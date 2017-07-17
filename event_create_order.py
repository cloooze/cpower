#!/usr/bin/env python

import sqlite3
import ecm_util as ecm_util
import nso_util as nso_util
import config as c
from event import Event
from utils import *
from ecm_exception import *
import time

INTERNAL_ERROR = '100'
REQUEST_ERROR = '200'
NETWORK_ERROR = '300'


class CreateOrder(Event):
    def __init__(self, order_status, order_id, source_api, order_json):
        super(CreateOrder, self).__init__()

        self.order_json = order_json
        self.order_status = order_status
        self.order_id = order_id
        self.source_api = source_api

    def notify(self):
        pass

    def execute(self):
        # Getting customer order params from getOrder response
        custom_order_params = dict()
        try:
            custom_order_params = self.order_json['data']['order']['customOrderParams']  # check if it throws exception
        except KeyError:
            # The flow ends up here when has been sent a creteVlink as createOrder from the customworkflow since
            # the order doesn't have any customOrderParams
            pass

        if self.order_status == 'ERR':
            self.logger.error(self.order_json['data']['order']['orderMsgs'])

        # CREATE SERVICE submitted by NSO
        create_service = get_order_items('createService', self.order_json, 1)
        create_vlink = get_order_items('createVLink', self.order_json, 1)

        if create_service is not None:
            # Processing post-createService (sub by NSO)
            customer_id = get_custom_order_param('Cust_Key', custom_order_params)
            rt_left = get_custom_order_param('rt-left', custom_order_params)
            rt_right = get_custom_order_param('rt-right', custom_order_params)
            rt_mgmt = get_custom_order_param('rt-mgmt', custom_order_params)
            vnf_list = get_custom_order_param('vnf_list', custom_order_params).split(',')

            operation_error = {'operation': 'createService', 'result': 'failure', 'customer-key': customer_id}
            workflow_error = {'operation': 'genericError', 'customer-key': customer_id}

            if self.order_status == 'ERR':
                nso_util.notify_nso(operation_error)
                return 'FAILURE'

            # Checking if the needed custom order params are empty
            empty_custom_order_param = get_empty_param(customer_id=customer_id, rt_left=rt_left,
                                                       rt_right=rt_right, rt_mgmt=rt_mgmt)

            if empty_custom_order_param is not None:
                error_message = "Custom order parameter [%s] mandatory but not found or empty in the request." % empty_custom_order_param
                self.logger.error(error_message)
                workflow_error['error-code'] = REQUEST_ERROR
                workflow_error['error-message'] = error_message
                nso_util.notify_nso(workflow_error)
                return 'FAILURE'

            service_id, service_name = create_service['id'], create_service['name']

            # We got everything we need to proceed:
            # Saving customer and network service info to DB. A check is not needed as NSO should send a
            # createService only in case of first VNF creation. This means there should not be customer and service
            # already.
            try:
                self.dbman.save_customer((customer_id, customer_id + '_name'))
            except sqlite3.IntegrityError:
                # Customer already in DB, it shouldn't be possible for createService operation unless the request is
                # re-submitted after a previous request that encountered an error
                pass

            ntw_service_row = (service_id, customer_id, service_name, rt_left, rt_right, rt_mgmt, '', '', '')
            try:
                self.dbman.save_network_service(ntw_service_row)
                self.logger.info('Network Service \'%s\' successfully stored into database.' % service_id)
            except sqlite3.IntegrityError:
                # Same as for customer
                pass

            # Create order

            # TODO to move in config
            csr1000_image_name = 'csr1000v-universalk9.16.04.01'
            fortinet_image_name = 'todo'
            vmhd_name = '2vcpu_4096MBmem_40GBdisk'

            order_items = list()

            order_items.append(get_create_vn('99', c.ecm_vdc_id, customer_id + '-left', 'Virtual Network left'))
            order_items.append(get_create_vn('100', c.ecm_vdc_id, customer_id + '-right', 'Virtual Network right'))

            i = 1
            for vnf_type in vnf_list:
                vnf_type = vnf_type.strip()
                order_items.append(
                    get_create_vapp(str(i), customer_id + '-' + vnf_type, c.ecm_vdc_id, 'Cpower', service_id))
                order_items.append(
                    get_create_vm(str(i + 1), c.ecm_vdc_id, customer_id + vnf_type, csr1000_image_name, vmhd_name,
                                  str(i)))
                order_items.append(
                    get_create_vmvnic(str(i + 2), customer_id + '-' + vnf_type + '-left', '99', str(i + 1), 'desc'))
                order_items.append(
                    get_create_vmvnic(str(i + 3), customer_id + '-' + vnf_type + '-right', '100', str(i + 1), 'desc'))
                # order_items.append(get_create_vmvnic(str(i+4), customer_id + '-' + vnf_type + '-mgmt', '', str(i+1), 'desc', c.mgmt_vn_id))
                i += 4  # TODO change to 5 uncomment

            order = dict(
                {
                    "tenantName": c.ecm_tenant_name,
                    "customOrderParams": [get_cop('service_id', service_id), get_cop('customer_id', customer_id),
                                          get_cop('rt-left', rt_left), get_cop('rt-right', rt_right)],
                    "orderItems": order_items
                }
            )

            try:
                ecm_util.invoke_ecm_api(None, c.ecm_service_api_orders, 'POST', order)
            except (ECMReqStatusError, ECMConnectionError) as e:
                self.logger.exception(e)
                operation_error['operation'] = 'createVnf'
                nso_util.notify_nso(operation_error)
                return 'FAILURE'
        elif create_vlink is not None:
            if self.order_status == 'ERR':
                self.logger.info('Could not create VLink. Rollbacking VNFs creation...')

                service_id = create_vlink['service']['id']

                # Getting the ntw_policy_rule list
                self.dbman.get_network_service(service_id)
                l = self.dbman.fetchone()['ntw_policy']
                original_vnf_type_list = list()
                if len(l) > 0:
                    original_vnf_type_list = l.split(',')

                # Getting current VNFs
                current_vnf_type_list = self.dbman.query('SELECT vnf_type,vnf_id '
                                                         'FROM vnf '
                                                         'WHERE ntw_service_id = ?', (service_id,)).fetchall()

                # Determining VNFs to delete/to keep
                vnf_to_delete = list()
                vnf_to_keep = list()

                for current_vnf_type in current_vnf_type_list:
                    if current_vnf_type['vnf_type'] in original_vnf_type_list:
                        vnf_to_keep.append(current_vnf_type['vnf_id'])
                    else:
                        vnf_to_delete.append(current_vnf_type['vnf_id'])

                self.logger.info('Deleting the VNFs: %s' % vnf_to_delete)
                self.logger.info('Dissociating the VNFs from the Service %s first.' % service_id)

                # Dissociating VNFs to delete from Network Service
                modify_service_json = load_json_file('./json/modify_service.json')

                for vnf_id in vnf_to_keep:
                    modify_service_json['vapps'].append({'id': vnf_id})

                modify_service_json['customInputParams'].append(get_cop('next_action', 'skip'))

                ecm_util.invoke_ecm_api(service_id, c.ecm_service_api_services, 'PUT', modify_service_json)

                time.sleep(5)

                # Deleting VNFs
                for vnf_id in vnf_to_delete:
                    ecm_util.invoke_ecm_api(vnf_id, c.ecm_service_api_vapps, 'DELETE')

                # Retrieving customer_id for NSO notification
                self.dbman.get_network_service(service_id)
                customer_id = self.dbman.fetchone()['customer_id']

                # TODO Notify NSO
                # operation_error['operation'] = 'createVnf'
                # nso_util.notify_nso(operation_error)
                # return 'FAILURE'
            else:
                # Processing post-createVLink (sub by CW)
                service_id = create_vlink['service']['id']
                ex_input = json.loads(create_vlink['customInputParams'][0]['value'])
                policy_rule = ex_input['extensions-input']['network-policy']['policy-rule']
                vlink_id, vlink_name = create_vlink['id'], create_vlink['name']

                # Updating Network Service table
                self.dbman.query('UPDATE network_service '
                                 'SET vlink_id = ?, vlink_name = ?, ntw_policy = ?  '
                                 'WHERE ntw_service_id = ?', (vlink_id, vlink_name, ','.join(policy_rule), service_id))

                self.logger.info('VLink %s with id %s succesfully created.' % (vlink_name, vlink_id))
                self.logger.info('Policy Rule %s successfully stored into database.' % policy_rule)

                self.logger.info('MOCK - Notifyin NSO SUCCESS')
        elif get_custom_order_param('next_action', custom_order_params) == 'delete_vnf':
            if self.order_status == 'COM':
                vnf_type_list_to_delete = get_custom_order_param('vnf_list', custom_order_params)
                customer_id = get_custom_order_param('customer_id', custom_order_params)
                service_id = get_custom_order_param('service_id', custom_order_params)

                placeholders = ','.join('?' for vnf in vnf_type_list_to_delete)
                res = self.dbman.query('SELECT vnf_id '
                                       'FROM vnf '
                                       'WHERE ntw_service_id = ? '
                                       'AND vnf_type IN (%s)' % placeholders).fetchall()

                self.logger.info('Deleting VNFs: %s ' % vnf_type_list_to_delete)
                for row in res:
                    ecm_util.invoke_ecm_api(row['vnf_id'], c.ecm_service_api_vapps, 'DELETE')

        else:
            # Processing post-createOrder (sub by CW)
            customer_id = get_custom_order_param('customer_id', custom_order_params)
            service_id = get_custom_order_param('service_id', custom_order_params)

            if customer_id is None or service_id is None:
                self.logger.info('Received an order not handled by the Custom Workflow. Skipping execution...')
                return

            operation_error = {'operation': 'createVnf', 'result': 'failure', 'customer-key': customer_id}
            # workflow_error = {'operation': 'genericError', 'customer-key': customer_id}

            if self.order_status == 'ERR':
                nso_util.notify_nso(operation_error)
                return 'FAILURE'

            # Saving VN_GROUP first
            create_vns = get_order_items('createVn', self.order_json)
            # If create_vns is None it means that the order was related to the creation of an addition VNF (ADD)
            if create_vns is not None:
                ADD_VNF_SCENARIO = False
                for vn in create_vns:
                    if 'left' in vn['name']:
                        vn_id_l = vn['id']
                        vn_name_l = vn['name']
                        r = ecm_util.invoke_ecm_api(vn_id_l, c.ecm_service_api_vns, 'GET')
                        resp = json.loads(r.text)
                        vn_vimobject_id_l = resp['data']['vn']['vimObjectId']
                    else:
                        vn_id_r = vn['id']
                        vn_name_r = vn['name']
                        r = ecm_util.invoke_ecm_api(vn_id_r, c.ecm_service_api_vns, 'GET')
                        resp = json.loads(r.text)
                        vn_vimobject_id_r = resp['data']['vn']['vimObjectId']

                self.logger.info('Saving VN_GROUP info into database.')
                vn_group_row = (vn_id_l, vn_name_l, vn_vimobject_id_l, vn_id_r, vn_name_r, vn_vimobject_id_r)
                vn_group_id = self.dbman.save_vn_group(vn_group_row, False)

            else:
                ADD_VNF_SCENARIO = True
                res = self.dbman.query('SELECT vnf.vn_group_id, vn_group.vn_left_name, vn_group.vn_right_name '
                                       'FROM vnf, vn_group '
                                       'WHERE vnf.ntw_service_id = ? '
                                       'AND vnf.vn_group_id = vn_group.vn_group_id',
                                       (service_id,)).fetchone()
                vn_group_id = res['vn_group_id']
                vn_name_l = res['vn_left_name']
                vn_name_r = res['vn_right_name']

            # Saving the remainder
            create_vnfs = get_order_items('createVapp', self.order_json)
            vnf_type_list = list()
            position = 0
            for vnf in create_vnfs:
                position += 1
                vnf_id, vnf_name, vnf_type = vnf['id'], vnf['name'], vnf['name'].split('-')[1]
                vnf_type_list.append(vnf_type)

                create_vms = get_order_items('createVm', self.order_json)

                for vm in create_vms:
                    if vm['vapp']['name'] == vnf_name:
                        vm_id, vm_name = vm['id'], vm['name']

                create_vmvnics = get_order_items('createVmVnic', self.order_json)

                for vmvnic in create_vmvnics:
                    if vmvnic['vm']['name'] == vm_name:
                        if 'left' in vmvnic['vn']['name']:
                            vmvnic_id_l, vmvnic_name_l = vmvnic['id'], vmvnic['name']
                            r = ecm_util.invoke_ecm_api(vmvnic_id_l, c.ecm_service_api_vmvnics, 'GET')
                            resp = json.loads(r.text)
                            vmvnic_ip_l = resp['data']['vmVnic']['internalIpAddress'][0]
                            vmvnic_vimobjectid_l = resp['data']['vmVnic']['vimObjectId']

                        else:
                            vmvnic_id_r, vmvnic_name_r = vmvnic['id'], vmvnic['name']
                            r = ecm_util.invoke_ecm_api(vmvnic_id_r, c.ecm_service_api_vmvnics, 'GET')
                            resp = json.loads(r.text)
                            vmvnic_ip_r = resp['data']['vmVnic']['internalIpAddress'][0]
                            vmvnic_vimobjectid_r = resp['data']['vmVnic']['vimObjectId']

                # Save VNF
                self.logger.info('Saving VNF info into database.')
                vnf_row = (vnf_id, service_id, vn_group_id, vnf_type, str(position), 'YES')
                self.dbman.save_vnf(vnf_row, False)

                # Save VM
                self.logger.info('Saving VM info into database.')
                vm_row = (vm_id, vnf_id, vm_name)
                self.dbman.save_vm(vm_row, False)

                # Save VMVNIC
                self.logger.info('Saving VMVNIC info into database.')
                vmvnic_row_l = (vmvnic_id_l, vm_id, vmvnic_name_l, vmvnic_ip_l, vmvnic_vimobjectid_l)
                vmvnic_row_r = (vmvnic_id_r, vm_id, vmvnic_name_r, vmvnic_ip_r, vmvnic_vimobjectid_r)
                self.dbman.save_vmvnic(vmvnic_row_l, False)
                self.dbman.save_vmvnic(vmvnic_row_r, False)

            self.dbman.commit()
            self.logger.info('All data succesfully save into database.')

            # TODO in case of ADD new VNF, send a modifyService to associate all the VNFs to the NetworkService

            # Creating VLINK
            # TODO adapt this in order to handle the MODIFY VLINK as well
            if ADD_VNF_SCENARIO is True:
                self.logger.info('Modifying VLINK object...')
                self.logger.info('MOCK not implmenented yet...')
                # TODO load mofify_vlink JSON and put in ex input modify
            else:
                self.logger.info('Creating VLINK object...')

                vlink_json = load_json_file('json/create_vlink.json')
                vlink_json['orderItems'][0]['createVLink']['name'] = customer_id + '-SDN-policy'
                vlink_json['orderItems'][0]['createVLink']['service']['id'] = service_id

                ex_input = load_json_file('json/extensions_input_create.json')

                # In case of multiple VNF, duplicate the entire service-instance tag
                policy_rule_list = list()

                for vnf_type_el in vnf_type_list:
                    # not really needed, vmvnic_name is always customer_id-vnf_type-left/right
                    cur = self.dbman.query('SELECT vmvnic.vm_vnic_name '
                                           'FROM vmvnic, vm, network_service, vnf '
                                           'WHERE network_service.customer_id = ? '
                                           'AND vnf.ntw_service_id = network_service.ntw_service_id '
                                           'AND vnf.vnf_type = ? '
                                           'AND vnf.vnf_id = vm.vnf_id '
                                           'AND vmvnic.vm_id = vm.vm_id', (customer_id, vnf_type_el))

                    rows = cur.fetchall()

                    service_instance = {
                        'operation': 'create',
                        'si_name': customer_id + '-' + vnf_type_el,
                        'left_virtual_network_fqdn': 'default-domain:cpower:' + vn_name_l,
                        'right_virtual_network_fqdn': 'default-domain:cpower:' + vn_name_r,
                        'service_template': 'cpower-template',
                        'port-tuple': {
                            'name': 'porttuple-' + customer_id + '-' + vnf_type_el,
                            'si-name': customer_id + '-' + vnf_type_el
                        },
                        'update-vmvnic': {
                            'left': (
                            rows[0]['vm_vnic_name'] if 'left' in rows[0]['vm_vnic_name'] else rows[1]['vm_vnic_name']),
                            'right': (
                            rows[0]['vm_vnic_name'] if 'right' in rows[0]['vm_vnic_name'] else rows[1]['vm_vnic_name']),
                            'port-tuple': 'porttuple-' + customer_id + '-' + vnf_type
                        }
                    }

                    ex_input['extensions-input']['service-instance'].append(service_instance)

                    policy_rule_list.append(customer_id + '-' + vnf_type_el)

                ex_input['extensions-input']['network-policy']['policy_name'] = customer_id + '_policy'
                ex_input['extensions-input']['network-policy']['src_address'] = 'default-domain:cpower:' + vn_name_l
                ex_input['extensions-input']['network-policy']['dst_address'] = 'default-domain:cpower:' + vn_name_r

                ex_input['extensions-input']['update-vn-RT']['right_VN'] = vn_vimobject_id_r
                ex_input['extensions-input']['update-vn-RT']['right_RT'] = get_custom_order_param('rt-right',
                                                                                                  custom_order_params)
                ex_input['extensions-input']['update-vn-RT']['left_VN'] = vn_vimobject_id_l
                ex_input['extensions-input']['update-vn-RT']['left_RT'] = get_custom_order_param('rt-left',
                                                                                                 custom_order_params)
                ex_input['extensions-input']['update-vn-RT'][
                    'network_policy'] = 'default-domain:cpower:' + customer_id + '_policy'

                ex_input['extensions-input']['network-policy']['policy-rule'] = policy_rule_list

                vlink_json['orderItems'][0]['createVLink']['customInputParams'][0]['value'] = json.dumps(ex_input)

                try:
                    ecm_util.invoke_ecm_api(None, c.ecm_service_api_orders, 'POST', vlink_json)
                except ECMConnectionError as e:
                    self.logger.exception(e)
                    # TODO notify NSO
                    return 'FAILURE'
