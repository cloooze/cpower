#!/usr/bin/env python

import sqlite3
import logging.config
import ecm_util as ecm_util
import nso_util as nso_util
from db_manager import DBManager
from ecm_exception import *
from nso_exception import *
import config as c
from event_manager import OrderManager


INTERNAL_ERROR = '100'
REQUEST_ERROR = '200'
NETWORK_ERROR = '300'


class ModifyService(OrderManager):

    def __init__(self, order_status, order_id, source_api, order_json):
        self.order_json = order_json
        self.order_status = order_status
        self.order_id = order_id
        self.source_api = source_api
        self.dbman = DBManager()
        logger = logging.getLogger('cpower')

    def execute(self):
        customer_id = get_custom_input_param('Cust_Key', get_custom_input_params('modifyService', order_json))

        operation_error = {'operation': 'createService', 'result': 'failure', 'customer-key': customer_id}
        workflow_error = {'operation': 'genericError', 'customer-key': customer_id}

        if order_status == 'ERR':
            nso_util.notify_nso(operation_error)
            _exit('FAILURE')

        if get_custom_input_param('source', get_custom_input_params('modifyService', order_json)) == 'workflow':
            service = get_order_items('modifyService', order_json)[0]
            service_id = service['id']
            vnf_id = service['vapps'][0]['id']

            # Associate service network - vnf into DB
            dbman.query('UPDATE vnf SET ntw_service_binding=? WHERE vnf_id=?', ('YES', vnf_id))

            # Getting VM id from DB, and get vimObjectId from ECM (/vms API)
            dbman.query('SELECT * FROM vm WHERE vnf_id=?', (vnf_id,))
            row = dbman.fetchone()
            vm_id = row['vm_id']
            vm_vnic1_id = row['vm_vnic1_id']
            vm_vnic1_name = row['vm_vnic1_name']
            vm_vnic2_id = row['vm_vnic2_id']
            vm_vnic2_name = row['vm_vnic2_name']

            try:
                # Getting vmvnics /vmvnics/<vmvnic_id> detail in order to get and store vmvnic_vimobject_id
                resp = ecm_util.invoke_ecm_api(vm_vnic1_id, c.ecm_service_api_vmvnics, 'GET')
                vmvnics_json = json.loads(resp.text)
                vm_vnic1_vimobject_id = vmvnics_json['data']['vmVnic']['vimObjectId']

                resp = ecm_util.invoke_ecm_api(vm_vnic2_id, c.ecm_service_api_vmvnics, 'GET')
                vmvnics_json = json.loads(resp.text)
                vm_vnic2_vimobject_id = vmvnics_json['data']['vmVnic']['vimObjectId']
            except (ECMReqStatusError, ECMConnectionError) as e:
                logger.exception(e)
                nso_util.notify_nso(operation_error)
                _exit('FAILURE')

            dbman.query('UPDATE vm SET vm_vnic1_vimobject_id=?,vm_vnic2_vimobject_id=? WHERE vm_id=?',
                        (vm_vnic1_vimobject_id, vm_vnic2_vimobject_id, vm_id))

            # Checking if VLinks already exists for the network_service
            dbman.query("SELECT * FROM network_service WHERE customer_id=? AND vlink_id IS NOT ''", (customer_id,))
            row = dbman.fetchone()

            if not row:  # Creating vLinks
                # Getting rt_left rt_right
                dbman.query("SELECT * FROM network_service WHERE customer_id=? AND vlink_id IS ''", (customer_id,))
                row = dbman.fetchone()
                rt_left = row['rt_left']
                rt_right = row['rt_right']
                # Getting VNs info
                dbman.query('SELECT * FROM vn_group WHERE vnf_id=?', (vnf_id,))
                row = dbman.fetchone()
                vn_left_name = row['vn_left_name']
                vn_right_name = row['vn_right_name']
                vn_left_vim_object_id = row['vn_left_vimobject_id']
                vn_right_vim_object_id = row['vn_right_vimobject_id']
                # Getting VNF type
                dbman.query('SELECT vnf_type FROM vnf WHERE vnf_id=?', (vnf_id,))
                row = dbman.fetchone()
                vnf_type = row['vnf_type']
                # Creating VLinks and CPs
                vlink_json = load_json_file('json/create_vlink.json')
                vlink_json['orderItems'][0]['createVLink']['name'] = customer_id + '-SDN-policy'
                vlink_json['orderItems'][0]['createVLink']['service']['id'] = service_id

                extensions_input_create = load_json_file('json/extensions_input_create.json')
                extensions_input_create['extensions-input']['service-instance'][
                    'si_name'] = customer_id + '-' + vnf_type
                extensions_input_create['extensions-input']['service-instance'][
                    'left_virtual_network_fqdn'] = 'default-domain:cpower:' + vn_left_name
                extensions_input_create['extensions-input']['service-instance'][
                    'right_virtual_network_fqdn'] = 'default-domain:cpower:' + vn_right_name
                extensions_input_create['extensions-input']['service-instance']['port-tuple'][
                    'name'] = 'port-tuple' + customer_id + '-' + vnf_id
                extensions_input_create['extensions-input']['service-instance']['port-tuple'][
                    'si_name'] = customer_id + '-' + vnf_type
                extensions_input_create['extensions-input']['service-instance']['update-vmvnic']['left'] = (
                vm_vnic1_vimobject_id if 'left' in vm_vnic1_name else vm_vnic2_vimobject_id)
                extensions_input_create['extensions-input']['service-instance']['update-vmvnic']['right'] = (
                vm_vnic2_vimobject_id if 'right' in vm_vnic2_name else vm_vnic1_vimobject_id)
                extensions_input_create['extensions-input']['service-instance']['update-vmvnic'][
                    'port-tuple'] = 'port-tuple' + customer_id + '-' + vnf_id
                extensions_input_create['extensions-input']['update-vn-RT']['right_VN'] = vn_right_vim_object_id
                extensions_input_create['extensions-input']['update-vn-RT']['right_RT'] = rt_right
                extensions_input_create['extensions-input']['update-vn-RT']['left_VN'] = vn_left_vim_object_id
                extensions_input_create['extensions-input']['update-vn-RT']['left_RT'] = rt_left
                extensions_input_create['extensions-input']['update-vn-RT'][
                    'network_policy'] = 'default-domain:cpower:' + customer_id + '_policy'
                extensions_input_create['extensions-input']['network-policy']['policy_name'] = customer_id + '_policy'
                extensions_input_create['extensions-input']['network-policy'][
                    'src_address'] = 'default-domain:cpower:' + vn_left_name
                extensions_input_create['extensions-input']['network-policy'][
                    'dst_address'] = 'default-domain:cpower:' + vn_right_name
                l = list()
                l.append(customer_id + '-' + vnf_id)
                extensions_input_create['extensions-input']['network-policy']['policy-rule'] = l

                vlink_json['orderItems'][0]['createVLink']['customInputParams'][0]['value'] = json.dumps(
                    extensions_input_create)

                try:
                    ecm_util.invoke_ecm_api(None, c.ecm_service_api_orders, 'POST', vlink_json)
                except ECMConnectionError as e:
                    logger.exception(e)
                    # TODO notify NSO
                    _exit('FAILURE')
            else:  # Modifying Vlinks
                # TODO
                # invoke the modifyVlink with ex input extensions_input_modify
                pass
            '''
            elif get_custom_input_param('vnf-position', get_custom_input_params('modifyService', order_json)) == '1':
                # Modifying... TODO to reimplement from skretch
                vlink_id = row['vlink_id']
                modify_vlink_json = load_json_file('json/modify_vlink.json')
                extensions_input_modify = load_json_file('json/extensions_input_modify.json')
                # TODO filliong ex inputs
                modify_vlink_json['customInputParams'][0]['value'] = str(extensions_input_modify)
                try:
                    ecm_util.invoke_ecm_api(vlink_id, c.ecm_service_api_vlinks, 'PUT', modify_vlink_json)
                except (ECMReqStatusError, ECMConnectionError) as e:
                    logger.exception(e)
                    nso_util.notify_nso(operation_error)
                    _exit('FAILURE')
            elif get_custom_input_param('vnf-position', get_custom_input_params('modifyService', order_json)) == '2':
                # TODO
                pass
            '''
        else:
            modify_service_cip = get_custom_input_params('modifyService', order_json)

            customer_id = get_custom_input_param('Cust_Key', modify_service_cip)
            vnf_type = get_custom_input_param('vnf_type', modify_service_cip)

            # Checking if the needed custom order params are empty
            empty_cop = get_empty_param(customer_id=customer_id, vnf_type=vnf_type)

            if empty_cop is not None:
                error_message = "Custom input parameter '%s' not found or empty." % empty_cop
                logger.error(error_message)
                workflow_error['error-code'] = REQUEST_ERROR
                workflow_error['error-message'] = error_message
                nso_util.notify_nso(workflow_error)
                _exit('FAILURE')
            if get_custom_input_param('operation', get_custom_input_params('modifyService', order_json)) == 'create':
                try:
                    ovf_package_id = get_ovf_package_id(vnf_type, 'add')
                except VnfTypeException:
                    error_message = 'VNF Type \'%s\' is not supported.' % vnf_type
                    logger.error(error_message)
                    workflow_error['error-code'] = REQUEST_ERROR
                    workflow_error['error-message'] = error_message
                    nso_util.notify_nso(workflow_error)
                    _exit('FAILURE')

                deploy_ovf_package_file = './json/deploy_ovf_package.json'
                ovf_package_json = load_json_file(deploy_ovf_package_file)
                ovf_package_json['tenantName'] = c.ecm_tenant_name
                ovf_package_json['vdc']['id'] = c.ecm_vdc_id
                ovf_package_json['ovfPackage']['namePrefix'] = customer_id + '-'

                logger.info('Deploying OVF Package %s' % ovf_package_id)

                try:
                    ecm_util.deploy_ovf_package(ovf_package_id, ovf_package_json)
                except (ECMReqStatusError, ECMConnectionError) as e:
                    logger.exception(e)
                    nso_util.notify_nso(operation_error)
                    _exit('FAILURE')
                    # TODO to check here is position tag is specified!!!! c   un problerma, non pu essere fatto qui
                    # TODO settare temporaneamnete la position, e fissarla solo se il deploy e andato bene


            elif get_custom_input_param('operation', get_custom_input_params('modifyService', order_json)) == 'delete':
                # Getting service_id from order
                service_id = get_order_items('modifyService')[0]['id']
                # Getting vnf_id from VNF table
                dbman.query('SELECT vnf_id FROM vnf WHERE ntw_service_id=? AND vnf_type IS NOT ?',
                            (service_id, vnf_type))
                vnf_ids = dbman.fetchall()
                if vnf_ids is not None:
                    # Detaching the VNF from Network Service in order to delete the VNF
                    json_data = load_json_file('json/modify_service.json')
                    json_data.pop('customInputParams')  # removing customInputParams from JSON
                    for vnf_id in vnf_ids:
                        json_data['vapps'].append({"id": vnf_id})
                    try:
                        ecm_util.invoke_ecm_api(service_id, c.ecm_service_api_services, 'PUT', json_data)
                    except:
                        # TODO
                        pass

                # Sleep 5sec
                # Deleting the VNF
                dbman.query('SELECT * FROM vnf WHERE ntw_service_id=? AND vnf_type=?', (service_id, vnf_type))
                row = dbman.fetchone()
                if row is not None:
                    row = dbman.fetchone()
                    vnf_id = row['vnf_id']
                    try:
                        ecm_util.invoke_ecm_api(vnf_id, c.ecm_service_api_vapps, 'DELETE')
                        # check if the delete fails because of the detach failed
                    except:
                        # TODO
                        pass
