#!/usr/bin/env python

import ecm_util as ecm_util
import nso_util as nso_util
import config as c
from event import Event
from utils import *
from ecm_exception import *


class CreateOrder(Event):
    def __init__(self, order_status, order_id, source_api, order_json):
        super(CreateOrder, self).__init__()

        self.order_json = order_json
        self.order_status = order_status
        self.order_id = order_id
        self.source_api = source_api

    def notify(self):
        if self.order_status == 'ERR':
            customer_id = self.event_params['customer_id']
            temp_vnf_id = self.event_params['temp_vnf_id']

            nso_util.notify_nso('createService', nso_util.get_create_vnf_data_response('failed', customer_id))

            self.dbman.set_notify_nso('YES', temp_vnf_id)

        if self.event_params['add_vnf_scenario']:
            # TODO notify NSO
            pass

    def execute(self):
        # Getting customer order params from getOrder response
        try:
            custom_order_params = self.order_json['data']['order']['customOrderParams']
            customer_id = get_custom_order_param('customer_id', custom_order_params)
            service_id = get_custom_order_param('service_id', custom_order_params)
            temp_vnf_id = get_custom_order_param('temp_vnf_id', custom_order_params)
        except KeyError:
            self.logger.info('Received an order not handled by the Custom Workflow. Skipping execution...')
            return

        self.event_params = {'service_id': service_id, 'customer_id': customer_id, 'temp_vnf_id': temp_vnf_id}

        if get_custom_order_param('next_action', custom_order_params) == 'delete_vnf':
            vnf_type_list_to_delete = get_custom_order_param('vnf_list', custom_order_params)

            if self.order_status == 'ERR':
                self.dbman.query('UPDATE vnf SET vnf_operation = ?, vnf_status = ? WHERE ntw_service_id = ? AND '
                                 'vnf_operation = ? AND vnf_status = ?', ('CREATE', 'COMPLETE', service_id, 'DELETE',
                                                                          'PENDING'))
            else:
                placeholders = ','.join('?' for vnf in vnf_type_list_to_delete)

                res = self.dbman.query('SELECT vnf_id '
                                       'FROM vnf '
                                       'WHERE ntw_service_id = ? '
                                       'AND vnf_type IN (%s)' % placeholders, tuple([service_id]) + tuple(vnf_type_list_to_delete.split(','))).fetchall()

                self.logger.info('Deleting VNFs: %s' % vnf_type_list_to_delete)

                for row in res:
                    ecm_util.invoke_ecm_api(row['vnf_id'], c.ecm_service_api_vapps, 'DELETE')

        # Processing post-createOrder (sub by CW)

        # Create order error, updating vnf table from database
        if self.order_status == 'ERR':
            self.logger.info('Order failed, updating VNF_STATUS column in VNF table.')
            self.dbman.query('UPDATE vnf SET vnf_status = ? WHERE ntw_service_id = ? AND vnf_status = ?', ('ERROR', service_id, 'PENDING'))
            return 'FAILURE'

        # Saving VN_GROUP first
        create_vns = get_order_items('createVn', self.order_json)

        # If create_vns is None it means that the order was related to the creation of an addition VNF (ADD)
        if create_vns is not None:
            add_vnf_scenario = False
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
            add_vnf_scenario = True
            res = self.dbman.query('SELECT vnf.vn_group_id, vn_group.vn_left_name, vn_group.vn_right_name '
                                   'FROM vnf, vn_group '
                                   'WHERE vnf.ntw_service_id = ? '
                                   'AND vnf.vn_group_id = vn_group.vn_group_id',
                                   (service_id,)).fetchone()
            vn_group_id = res['vn_group_id']
            vn_name_l = res['vn_left_name']
            vn_name_r = res['vn_right_name']

        self.event_params = {'add_vnf_scenario': add_vnf_scenario}

        # Saving the remainder
        create_vnfs = get_order_items('createVapp', self.order_json)
        vnf_type_list = list()

        for vnf in create_vnfs:
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
                    elif 'right' in vmvnic['vn']['name']:
                        vmvnic_id_r, vmvnic_name_r = vmvnic['id'], vmvnic['name']
                        r = ecm_util.invoke_ecm_api(vmvnic_id_r, c.ecm_service_api_vmvnics, 'GET')
                        resp = json.loads(r.text)
                        vmvnic_ip_r = resp['data']['vmVnic']['internalIpAddress'][0]
                        vmvnic_vimobjectid_r = resp['data']['vmVnic']['vimObjectId']
                    elif 'management' in vmvnic['vn']['name']:
                        vmvnic_id_mgmt, vmvnic_name_mgmt = vmvnic['id'], vmvnic['name']
                        r = ecm_util.invoke_ecm_api(vmvnic_id_mgmt, c.ecm_service_api_vmvnics, 'GET')
                        resp = json.loads(r.text)
                        vmvnic_ip_mgmt = resp['data']['vmVnic']['internalIpAddress'][0]
                        vmvnic_vimobjectid_mgmt = resp['data']['vmVnic']['vimObjectId']

            # Save VNF
            self.logger.info('Saving VNF info into database.')

            self.dbman.query('UPDATE vnf SET vnf_id = ?, vn_group_id = ?, ntw_service_binding = ?, vnf_status = ? '
                             'WHERE ntw_service_id = ? AND vnf_type = ? AND vnf_status = ?', (vnf_id, vn_group_id, 'YES',
                                                                           'COMPLETE', service_id, vnf_type, 'PENDING'))

            # Save VM
            self.logger.info('Saving VM info into database.')
            vm_row = (vm_id, vnf_id, vm_name)
            self.dbman.save_vm(vm_row, False)

            # Save VMVNIC
            self.logger.info('Saving VMVNIC info into database.')
            vmvnic_row_l = (vmvnic_id_l, vm_id, vmvnic_name_l, vmvnic_ip_l, vmvnic_vimobjectid_l)
            vmvnic_row_r = (vmvnic_id_r, vm_id, vmvnic_name_r, vmvnic_ip_r, vmvnic_vimobjectid_r)
            vmvnic_row_mgmt = (vmvnic_id_mgmt, vm_id, vmvnic_name_mgmt, vmvnic_ip_mgmt, vmvnic_vimobjectid_mgmt)
            self.dbman.save_vmvnic(vmvnic_row_l, False)
            self.dbman.save_vmvnic(vmvnic_row_r, False)
            self.dbman.save_vmvnic(vmvnic_row_mgmt, False)

        self.dbman.commit()
        self.logger.info('All data succesfully save into database.')

        # TODO in case of ADD new VNF, send a modifyService to associate all the VNFs to the NetworkService

        # Creating VLINK
        if add_vnf_scenario:
            self.logger.info('Modifying VLINK object...')
            self.logger.info('Skipping modify Vlink - NOT YET IMPLEMENTED IN ACTIVATION ADAPTER.')

            vlink_json = load_json_file('json/modify_vlink.json')
            ex_input = load_json_file('json/extensions_input_modify.json')

            self.dbman.query('SELECT ntw_policy FROM network_service WHERE ntw_service_id = ?', (service_id,))
            current_ntw_policy = self.dbman.fetchone()['ntw_policy'].split(',')

            for vnf_type_el in vnf_type_list:
                vm_vnic_name_left = customer_id + '-' + vnf_type_el + '-left'
                self.dbman.query('SELECT vm_vnic_vimobject_id FROM vmvnic WHERE vm_vnic_name=?', (vm_vnic_name_left, ))
                vm_vnic_vimobject_id_left = self.dbman.fetchone()['vm_vnic_vimobject_id']

                vm_vnic_name_right = customer_id + '-' + vnf_type_el + '-right'
                self.dbman.query('SELECT vm_vnic_vimobject_id FROM vmvnic WHERE vm_vnic_name=?', (vm_vnic_name_right,))
                vm_vnic_vimobject_id_right = self.dbman.fetchone()['vm_vnic_vimobject_id']

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
                        'left': vm_vnic_vimobject_id_left,
                        'right': vm_vnic_vimobject_id_right,
                        'port-tuple': 'porttuple-' + customer_id + '-' + vnf_type
                    }
                }

                ex_input['extensions-input']['service-instance'].append(service_instance)

                current_ntw_policy.append('default-domain:cpower:' + customer_id + '-' + vnf_type_el)

            ex_input['extensions-input']['network-policy']['policy_name'] = customer_id + '_policy'
            ex_input['extensions-input']['network-policy']['policy-rule'] = current_ntw_policy

            self.dbman.query('SELECT vn_left_vimobject_id, vn_right_vimobject_id FROM vn_group, vnf WHERE vnf.vnf_id=? AND vnf.vn_group_id = vn_group.vn_group_id', (vnf_id,))
            res = self.dbman.fetchone()

            ex_input['extensions-input']['update-vn-RT']['right_VN'] = res['vn_right_vimobject_id']
            ex_input['extensions-input']['update-vn-RT']['left_VN'] = res['vn_left_vimobject_id']

            vlink_json['customInputParams'][0]['value'] = json.dumps(ex_input)

            self.dbman.query('SELECT vlink_id FROM network_service WHERE ntw_service_id = ?', (service_id,))
            vlink_id = self.dbman.fetchone()['vlink_id']
            ecm_util.invoke_ecm_api(vlink_id, c.ecm_service_api_vlinks, 'PUT', vlink_json)

        else:
            self.logger.info('Creating VLINK object...')

            vlink_json = load_json_file('json/create_vlink.json')
            vlink_json['orderItems'][0]['createVLink']['name'] = customer_id + '-SDN-policy'
            vlink_json['orderItems'][0]['createVLink']['service']['id'] = service_id

            ex_input = load_json_file('json/extensions_input_create.json')

            # In case of multiple VNF, duplicating the entire service-instance tag
            policy_rule_list = list()

            for vnf_type_el in vnf_type_list:
                vm_vnic_name_left = customer_id + '-' + vnf_type_el + '-left'
                self.dbman.query('SELECT vm_vnic_vimobject_id FROM vmvnic WHERE vm_vnic_name=?', (vm_vnic_name_left,))
                vm_vnic_vimobject_id_left = self.dbman.fetchone()['vm_vnic_vimobject_id']

                vm_vnic_name_right = customer_id + '-' + vnf_type_el + '-right'
                self.dbman.query('SELECT vm_vnic_vimobject_id FROM vmvnic WHERE vm_vnic_name=?', (vm_vnic_name_right,))
                vm_vnic_vimobject_id_right = self.dbman.fetchone()['vm_vnic_vimobject_id']

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
                        'left': vm_vnic_vimobject_id_left,
                        'right': vm_vnic_vimobject_id_right
                    }
                }

                ex_input['extensions-input']['service-instance'].append(service_instance)

                policy_rule_list.append('default-domain:cpower:' + customer_id + '-' + vnf_type_el)

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

            ecm_util.invoke_ecm_api(None, c.ecm_service_api_orders, 'POST', vlink_json)

    def rollback(self):
        pass