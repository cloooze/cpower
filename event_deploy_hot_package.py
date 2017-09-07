#!/usr/bin/env python

import ecm_util as ecm_util
import nso_util as nso_util
import config as c
from ecm_exception import *
from event import Event
from utils import *


class DeployHotPackage(Event):

    def __init__(self, order_status, order_id, source_api, order_json):
        super(DeployHotPackage, self).__init__()

        self.order_json = order_json
        self.order_status = order_status
        self.order_id = order_id
        self.source_api = source_api

    def notify(self):
        pass

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
            # self.dbman.query('UPDATE vnf SET vnf_status=? WHERE vnf_type=? AND vnf_operation=? AND vnf_status=?', ('ERROR', vnf_type, 'CREATE', 'PENDING'), False)
            self.dbman.query('DELETE FROM vnf WHERE vnf_type=? AND vnf_operation=? AND vnf_status=?', (vnf_type, 'CREATE', 'PENDING'))

            self.dbman.query('SELECT vn_group_id FROM vnf WHERE vnf_type=? AND vnf_operation=? AND vnf_status=?', (vnf_type, 'CREATE', 'ERROR'))
            result = self.dbman.fetchone()
            self.event_params = {'vn_group_id': result['vn_group_id']}

            return 'FAILURE'


        # Updating just created VNF
        self.dbman.query('UPDATE vnf SET vnf_id=?, vnf_status=? WHERE vnf_type=? AND vnf_operation=? AND vnf_status=?', (vnf_id, 'COMPLETE',  vnf_type, 'CREATE', 'PENDING'), False)

        # Getting VM details
        r = ecm_util.invoke_ecm_api(vnf_id + '?$expand=vms', c.ecm_service_api_vapps, 'GET')
        resp = json.loads(r.text)

        vm_id = resp['data']['vapp']['vms'][0]['id']
        vm_name = resp['data']['vapp']['vms'][0]['name']

        # Getting VMVNIC details
        r = ecm_util.invoke_ecm_api(vm_id + '$expand=vmvnics', c.ecm_service_api_vms, 'GET')
        resp = json.loads(r.text)

        vmvnics_list = list()

        for vmvnic in resp['data']['vm']['vmVnics']:
            vmvnic_id = resp['data']['vm']['vmVnics'][0]['id']
            vmvnic_name = resp['data']['vm']['vmVnics'][0]['name']
            vmvnic_ip_address = vmvnic['internalIpAddress'][0]
            vmvnic_vim_object_id = vmvnic['vimObjectId']
            vmvnics_list.append(tuple(vmvnic_id, vm_id, vmvnic_name, vmvnic_ip_address, vmvnic_vim_object_id))

        # Saving everything into DB
        self.dbman.save_vm(tuple(vm_id, vnf_id, vm_name), False)
        self.dbman.save_vmvnic(vmvnics_list[0], False)
        self.dbman.save_vmvnic(vmvnics_list[1], False)
        self.dbman.save_vmvnic(vmvnics_list[2], False)

        self.dbman.commit()

        self.logger.info('All information about VM and VMVNICs successfully stored into DB.')



        # create VLINK
        # TODO




        # Checking if a second hot deploy is required
        self.dbman.query('SELECT vnf_type FROM network_service,vnf WHERE network_service.customer_id=? AND '
                         'network_service.ntw_service_id=vnf.ntw_service_id AND vnf.vnf_operation=? AND vnf.vnf_status=?', (customer_id, 'CREATE', 'PENDING'))
        result = self.dbman.fetchone()

        if result is not None:
            # DEPLOY HOT PACKAGE HERE
            vnf_type = result['vnf_type']
            hot_package_id = 'dd1f60a6-f735-412c-a10a-4f282a891ca2'  # TODO Put it in config
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

    def rollback(self):
        self.dbman.rollback() # to rollback manual insert into db in case of error

        self.logger.info('Rollbacking VNs creation...')

        vn_group_id = self.event_params['vn_gruop_id']

        ecm_util.invoke_ecm_api(vn_group_id, c.ecm_service_api_vns, 'DELETE')

        self.dbman.delete_vn_group(vn_group_id)


        # TODO
        # manually delete VN and NETWORK SERVICE(?)



