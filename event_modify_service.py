#!/usr/bin/env python

import ecm_util as ecm_util
import nso_util as nso_util
import config as c
from ecm_exception import *
from event_manager import EventManager
from utils import *


INTERNAL_ERROR = '100'
REQUEST_ERROR = '200'
NETWORK_ERROR = '300'


class ModifyService(EventManager):

    def __init__(self, order_status, order_id, source_api, order_json):
        super(ModifyService, self).__init__()

        self.order_json = order_json
        self.order_status = order_status
        self.order_id = order_id
        self.source_api = source_api

    def notify(self):
        pass

    def execute(self):
        modify_service_custom_input_params = get_custom_input_params('modifyService', self.order_json)
        customer_id = get_custom_input_param('Cust_Key', modify_service_custom_input_params)

        operation_error = {'operation': 'createService', 'result': 'failure', 'customer-key': customer_id}
        workflow_error = {'operation': 'genericError', 'customer-key': customer_id}

        if self.order_status == 'ERR':
            self.logger.error(self.order_json['data']['order']['orderMsgs'])
            nso_util.notify_nso(operation_error)
            return 'FAILURE'

        if get_custom_input_param('source', modify_service_custom_input_params) == 'workflow':
            modify_service = get_order_items('modifyService', self.order_json, 1)
            service_id, vnf_id = modify_service['id'], modify_service['vapps'][0]['id']

            # Associate service network - vnf into DB
            self.dbman.query('UPDATE vnf SET ntw_service_binding=? WHERE vnf_id=?', ('YES', vnf_id))

            # Getting VM id from DB, and get vimObjectId from ECM (/vms API)
            self.dbman.query('SELECT * FROM vm WHERE vnf_id=?', (vnf_id,))
            row = self.dbman.fetchone()
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
                self.logger.exception(e)
                nso_util.notify_nso(operation_error)
                return 'FAILURE'

            self.dbman.query('UPDATE vm SET vm_vnic1_vimobject_id=?,vm_vnic2_vimobject_id=? WHERE vm_id=?',
                        (vm_vnic1_vimobject_id, vm_vnic2_vimobject_id, vm_id))

            # Checking if VLinks already exists for the network_service
            self.dbman.query("SELECT * FROM network_service WHERE customer_id=? AND vlink_id IS NOT ''", (customer_id,))
            row = self.dbman.fetchone()

            if not row:  # Creating vLinks
                # Getting rt_left rt_right
                self.dbman.query("SELECT * FROM network_service WHERE customer_id=? AND vlink_id IS ''", (customer_id,))
                row = self.dbman.fetchone()
                rt_left = row['rt_left']
                rt_right = row['rt_right']
                # Getting VNs info
                self.dbman.query('SELECT * FROM vn_group WHERE vnf_id=?', (vnf_id,))
                row = self.dbman.fetchone()
                vn_left_name = row['vn_left_name']
                vn_right_name = row['vn_right_name']
                vn_left_vim_object_id = row['vn_left_vimobject_id']
                vn_right_vim_object_id = row['vn_right_vimobject_id']
                # Getting VNF type
                self.dbman.query('SELECT vnf_type FROM vnf WHERE vnf_id=?', (vnf_id,))
                row = self.dbman.fetchone()
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
                l.append(customer_id + '-' + vnf_type)
                extensions_input_create['extensions-input']['network-policy']['policy-rule'] = l

                vlink_json['orderItems'][0]['createVLink']['customInputParams'][0]['value'] = json.dumps(
                    extensions_input_create)

                try:
                    ecm_util.invoke_ecm_api(None, c.ecm_service_api_orders, 'POST', vlink_json)
                except ECMConnectionError as e:
                    self.logger.exception(e)
                    # TODO notify NSO
                    return 'FAILURE'
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
            vnf_type = get_custom_input_param('vnf_type', modify_service_custom_input_params)

            # Checking if the needed custom order params are empty
            empty_cop = get_empty_param(customer_id=customer_id, vnf_type=vnf_type)

            if empty_cop is not None:
                error_message = "Custom input parameter [%s] is needed but not found or empty in the request." % empty_cop
                self.logger.error(error_message)
                workflow_error['error-code'] = REQUEST_ERROR
                workflow_error['error-message'] = error_message
                nso_util.notify_nso(workflow_error)
                return 'FAILURE'

            if get_custom_input_param('operation', modify_service_custom_input_params) == 'create':
                try:
                    ovf_package_id = get_ovf_package_id(vnf_type, 'add')
                except VnfTypeException:
                    error_message = 'VNF Type [%s] is not supported.' % vnf_type
                    self.logger.error(error_message)
                    workflow_error['error-code'] = REQUEST_ERROR
                    workflow_error['error-message'] = error_message
                    nso_util.notify_nso(workflow_error)
                    return 'FAILURE'

                ovf_package_file = './json/deploy_ovf_package.json'
                ovf_package_json = load_json_file(ovf_package_file)
                ovf_package_json['tenantName'] = c.ecm_tenant_name
                ovf_package_json['vdc']['id'] = c.ecm_vdc_id
                ovf_package_json['ovfPackage']['namePrefix'] = customer_id + '-'

                self.logger.info('Deploying OVF Package %s' % ovf_package_id)

                try:
                    ecm_util.deploy_ovf_package(ovf_package_id, ovf_package_json)
                except (ECMReqStatusError, ECMConnectionError) as e:
                    self.logger.exception(e)
                    nso_util.notify_nso(operation_error)
                    return 'FAILURE'
                    # TODO to check here is position tag is specified!!!! c   un problerma, non pu essere fatto qui
                    # TODO settare temporaneamnete la position, e fissarla solo se il deploy e andato bene

            elif get_custom_input_param('operation', modify_service_custom_input_params) == 'delete':
                # Getting service_id from order
                service_id = get_order_items('modifyService', self.order_json, 1)['id']

                # Getting vnf_id from VNF table
                self.dbman.query('SELECT vnf_id FROM vnf WHERE ntw_service_id=? AND vnf_type IS NOT ?', (service_id, vnf_type))

                vnf_ids = self.dbman.fetchall()

                if vnf_ids is not None:
                    # Detaching the VNF from Network Service in order to delete the VNF
                    modify_service_json = load_json_file('json/modify_service.json')
                    modify_service_json.pop('customInputParams')  # removing customInputParams from JSON, not needed here

                    for vnf_id in vnf_ids:
                        modify_service_json['vapps'].append({"id": vnf_id})
                    try:
                        ecm_util.invoke_ecm_api(service_id, c.ecm_service_api_services, 'PUT', modify_service_json)
                    except:
                        # TODO
                        pass

                # Sleep 5sec, NEEDED??? to test

                # Deleting the VNF
                self.dbman.query('SELECT * FROM vnf WHERE ntw_service_id=? AND vnf_type=?', (service_id, vnf_type))
                row = self.dbman.fetchone()

                if row is not None:
                    row = self.dbman.fetchone()
                    vnf_id = row['vnf_id']
                    try:
                        ecm_util.invoke_ecm_api(vnf_id, c.ecm_service_api_vapps, 'DELETE')
                        # check if the delete fails because of the detach failed
                    except:
                        # TODO
                        pass
