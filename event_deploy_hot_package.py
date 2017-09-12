#!/usr/bin/env python

import ecm_util as ecm_util
import nso_util as nso_util
import config as c
from ecm_exception import *
from event import Event
from utils import *
import time


class DeployHotPackage(Event):

    def __init__(self, order_status, order_id, source_api, order_json):
        super(DeployHotPackage, self).__init__()

        self.order_json = order_json
        self.order_status = order_status
        self.order_id = order_id
        self.source_api = source_api

    def notify(self):
        if self.order_status == 'ERR':
            try:
                customer_id = self.order_json['data']['order']['orderItems'][0]['deployHotPackage']['name'].split('-')[1]
            except KeyError:
                self.logger.info('Received a request not handled by custom workflow. Skipping execution')
                return

            nso_util.notify_nso('createService', nso_util.get_create_vnf_data_response('failed', customer_id))

    def execute(self):
        # TODO
        # check if ERR
        # get VAPP details
        # get VM details
        # get VMVNIC details
        # save everything on DB
        # create VMVNIC

        customer_id = self.order_json['data']['order']['orderItems'][0]['deployHotPackage']['name'].split('-')[1]
        vnf_type = self.order_json['data']['order']['orderItems'][0]['deployHotPackage']['name'].split('-')[0]
        vnf_id = self.order_json['data']['order']['orderItems'][0]['deployHotPackage']['id']

        if self.order_status == 'ERR':
            self.dbman.query('SELECT vnf.ntw_service_id,vn_group.vn_group_id,vn_left_id,vn_right_id FROM vnf,vn_group WHERE '
                             'vnf.vnf_type=? AND vnf.vnf_operation=? AND vnf.vnf_status=? AND '
                             'vnf.vn_group_id=vn_group.vn_group_id', (vnf_type, 'CREATE', 'PENDING'))
            result = self.dbman.fetchone()
            self.event_params = {'service_id': result['ntw_service_id'],
                                 'vn_group_id': result['vn_group_id'],
                                 'vn_left_id': result['vn_left_id'],
                                 'vn_right_id': result['vn_right_id']}

            # self.dbman.query('UPDATE vnf SET vnf_status=? WHERE vnf_type=? AND vnf_operation=? AND vnf_status=?', ('ERROR', vnf_type, 'CREATE', 'PENDING'), False)
            self.dbman.query('DELETE FROM vnf WHERE vnf_operation=? AND vnf_status=?', ('CREATE', 'PENDING'))

            return 'FAILURE'

        # Updating just created VNF
        self.dbman.query('UPDATE vnf SET vnf_id=?, vnf_status=? WHERE vnf_type=? AND vnf_operation=? AND vnf_status=?', (vnf_id, 'COMPLETE',  vnf_type, 'CREATE', 'PENDING'))

        # Getting VM details
        r = ecm_util.invoke_ecm_api(vnf_id + '?$expand=vms', c.ecm_service_api_vapps, 'GET')
        resp = json.loads(r.text)

        vm_id = resp['data']['vapp']['vms'][0]['id']
        vm_name = resp['data']['vapp']['vms'][0]['name']

        # Getting VMVNIC details
        r = ecm_util.invoke_ecm_api(vm_id + '?$expand=vmvnics', c.ecm_service_api_vms, 'GET')
        resp = json.loads(r.text)

        vmvnics_list = list()

        for vmvnic in resp['data']['vm']['vmVnics']:
            vmvnic_id = vmvnic['id']
            vmvnic_name = vmvnic['name']
            vmvnic_ip_address = vmvnic['internalIpAddress'][0]
            vmvnic_vim_object_id = vmvnic['vimObjectId']
            vmvnics_list.append((vmvnic_id, vm_id, vmvnic_name, vmvnic_ip_address, vmvnic_vim_object_id))

        # Saving everything into DB
        self.dbman.save_vm((vm_id, vnf_id, vm_name), False)
        self.dbman.save_vmvnic(vmvnics_list[0], False)
        self.dbman.save_vmvnic(vmvnics_list[1], False)
        self.dbman.save_vmvnic(vmvnics_list[2], False)

        self.dbman.commit()

        self.logger.info('VM and VMVNICs information successfully stored into DB.')

        # Checking if a second hot deploy is required
        self.dbman.query('SELECT vnf_type FROM network_service,vnf WHERE network_service.customer_id=? AND '
                         'network_service.ntw_service_id=vnf.ntw_service_id AND vnf.vnf_operation=? AND vnf.vnf_status=?', (customer_id, 'CREATE', 'PENDING'))
        result = self.dbman.fetchone()

        if result is not None:
            # DEPLOY SECOND HOT PACKAGE HERE
            vnf_type = result['vnf_type']
            hot_package_id = c.hot_package_id  # TODO Put it in config
            hot_file_json = load_json_file('./json/deploy_hot_package.json')

            # Preparing the Hot file
            hot_file_json['tenantName'] = c.ecm_tenant_name
            hot_file_json['vdc']['id'] = c.ecm_vdc_id
            hot_file_json['hotPackage']['vapp']['name'] = vnf_type + '-' + customer_id
            hot_file_json['hotPackage']['vapp']['configData'][0]['value'] = customer_id + '-' + vnf_type
            hot_file_json['hotPackage']['vapp']['configData'][1]['value'] = customer_id + '-left'
            hot_file_json['hotPackage']['vapp']['configData'][2]['value'] = customer_id + '-right'
            hot_file_json['hotPackage']['vapp']['configData'][3]['value'] = c.mgmt_vn_name

            self.logger.info('Depolying HOT package %s' % hot_package_id)
            ecm_util.deploy_hot_package(hot_package_id, hot_file_json)
            return


        # CREATE VLINK
        # I need:
        # service_id
        # vnf type list
        # vn name left
        # vn name right
        # vn vimobject id left
        # vn vimobject id right

        # Getting service_id
        self.dbman.query('SELECT ntw_service_id FROM vnf WHERE vnf_id=?', (vnf_id,))
        result = self.dbman.fetchone()
        service_id = result['ntw_service_id']

        # Getting vnf type list
        self.dbman.query('SELECT vnf_type FROM vnf WHERE ntw_service_id=?', (service_id,))
        result = self.dbman.fetchall()
        vnf_type_list = list(r['vnf_type'] for r in result)

        # Building vn names
        vn_name_l = customer_id + '-' + 'left'
        vn_name_r = customer_id + '-' + 'right'

        # Getting vn vimobject IDs
        self.dbman.query('SELECT vn_left_vimobject_id,vn_right_vimobject_id FROM vn_group,vnf WHERE vnf.vnf_id=? AND vnf.vn_group_id = vn_group.vn_group_id', (vnf_id,))
        result = self.dbman.fetchone()
        vn_vimobject_id_l = result['vn_left_vimobject_id']
        vn_vimobject_id_r = result['vn_right_vimobject_id']

        # Getting route targets
        self.dbman.query('SELECT rt_left,rt_right,rt_mgmt FROM network_service WHERE ntw_service_id=?', (service_id,))
        result = self.dbman.fetchone()
        rt_left = result['rt_left']
        rt_right = result['rt_right']
        rt_mgmt = result['rt_mgmt']

        self.logger.info('Creating VLINK object...')

        vlink_json = load_json_file('json/create_vlink.json')
        vlink_json['orderItems'][0]['createVLink']['name'] = customer_id + '-SDN-policy'
        vlink_json['orderItems'][0]['createVLink']['service']['id'] = service_id

        ex_input = load_json_file('json/extensions_input_create.json')

        # In case of multiple VNF, duplicating the entire service-instance tag
        policy_rule_list = list()

        for vnf_type_el in vnf_type_list:
            # Getting vm_vnic_vimobject_id of left and right
            self.dbman.query('SELECT vm_vnic_vimobject_id FROM vmvnic,vm,vnf WHERE vnf.ntw_service_id=? AND '
                             'vnf.vnf_type=? AND vnf.vnf_id=vm.vnf_id AND vm.vm_id=vmvnic.vm_id AND '
                             'vmvnic.vm_vnic_name LIKE ?', (service_id, vnf_type_el, 'left%'))
            vm_vnic_vimobject_id_l = self.dbman.fetchone()['vm_vnic_vimobject_id']

            self.dbman.query('SELECT vm_vnic_vimobject_id FROM vmvnic,vm,vnf WHERE vnf.ntw_service_id=? AND '
                             'vnf.vnf_type=? AND vnf.vnf_id=vm.vnf_id AND vm.vm_id=vmvnic.vm_id AND vmvnic.vm_vnic_name LIKE ?',
                             (service_id, vnf_type_el, 'right%'))
            vm_vnic_vimobject_id_r = self.dbman.fetchone()['vm_vnic_vimobject_id']

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
                    'left': vm_vnic_vimobject_id_l,
                    'right': vm_vnic_vimobject_id_r
                }
            }

            ex_input['extensions-input']['service-instance'].append(service_instance)

            policy_rule_list.append('default-domain:cpower:' + customer_id + '-' + vnf_type_el)

        ex_input['extensions-input']['network-policy']['policy_name'] = customer_id + '_policy'
        ex_input['extensions-input']['network-policy']['src_address'] = 'default-domain:cpower:' + vn_name_l
        ex_input['extensions-input']['network-policy']['dst_address'] = 'default-domain:cpower:' + vn_name_r

        ex_input['extensions-input']['update-vn-RT']['right_VN'] = vn_vimobject_id_r
        ex_input['extensions-input']['update-vn-RT']['right_RT'] = rt_right.split(',')
        ex_input['extensions-input']['update-vn-RT']['left_VN'] = vn_vimobject_id_l
        ex_input['extensions-input']['update-vn-RT']['left_RT'] = rt_left.split(',')
        ex_input['extensions-input']['update-vn-RT'][
            'network_policy'] = 'default-domain:cpower:' + customer_id + '_policy'

        ex_input['extensions-input']['network-policy']['policy-rule'] = policy_rule_list

        vlink_json['orderItems'][0]['createVLink']['customInputParams'][0]['value'] = json.dumps(ex_input)

        ecm_util.invoke_ecm_api(None, c.ecm_service_api_orders, 'POST', vlink_json)

    def rollback(self):
        # if self.order_status == 'ERR' or self.event_params['rollback'] == 'YES':
        if self.order_status == 'ERR':
            self.logger.info('Checking if VNF rollback is needed...')
            self.dbman.rollback() # to rollback manual insert into db in case of error

            service_id = self.event_params['service_id']
            self.dbman.query('SELECT vnf.vnf_id,vm.vm_id FROM vnf,vm WHERE vnf.ntw_service_id=? AND vnf.vnf_status=? AND '
                             'vnf.vnf_operation=? AND vnf.nso_notify=?', (service_id, 'CREATE', 'COMPLETE', 'NO'))
            result = self.dbman.fetchall()

            for r in result:
                vnf_id = r['vnf_id']
                vm_id = r['vm_id']

                self.logger.info('Deleting VM %s' % vm_id)
                ecm_util.invoke_ecm_api(vm_id, c.ecm_service_api_vms, 'DELETE')

                self.logger.info('Waiting 40 secs to let VM remove operation to complete.')
                time.sleep(40)

                self.logger.info('Deleting VAPP %s' % vnf_id)
                ecm_util.invoke_ecm_api(vnf_id, c.ecm_service_api_vapps, 'DELETE')

            if result is not None:
                vn_left_id = self.event_params['vn_left_id']
                vn_right_id = self.event_params['vn_right_id']

                self.logger.info('Deleting VNs')
                ecm_util.invoke_ecm_api(vn_left_id, c.ecm_service_api_vns, 'DELETE') # what if it goes wrong?? :(
                ecm_util.invoke_ecm_api(vn_right_id, c.ecm_service_api_vns, 'DELETE')
            else:
                self.logger.info('Nothing to rollback.')



            # TODO
            # manually delete VN and NETWORK SERVICE(?)



