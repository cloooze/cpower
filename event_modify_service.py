#!/usr/bin/env python

import ecm_util as ecm_util
import nso_util as nso_util
import config as c
from ecm_exception import *
from event import Event
from utils import *
import time


class ModifyService(Event):

    def __init__(self, order_status, order_id, source_api, order_json):
        super(ModifyService, self).__init__()

        self.order_json = order_json
        self.order_status = order_status
        self.order_id = order_id
        self.source_api = source_api

    def notify(self):
        if self.order_status == 'ERR':
            self.logger.error('MOCK - notify NSO that modifyService request failed')
            # TODO need to handle the modifyService failure scenario

    def execute(self):
        modify_service = get_order_items('modifyService', self.order_json, 1)
        service_id = modify_service['id']

        if self.order_status == 'ERR':
            self.event_params = {'service_id': service_id}
            return 'FAILURE'

        modify_service_cip = get_custom_input_params('modifyService', self.order_json)

        if get_custom_input_param('next_action', modify_service_cip) == 'skip':
            self.logger.info('Nothing to do.')
            return

        # Getting customer_id, it will be used later
        self.dbman.query('SELECT customer_id FROM network_service WHERE ntw_service_id = ?', (service_id,))
        customer_id = self.dbman.fetchone()['customer_id']

        # Getting target vnf_list
        vnf_list = get_custom_input_param('vnf_list', modify_service_cip)
        if vnf_list is None:
            self.logger.error('Received an order not handled by the Custom Workflow. Skipping execution...')

        target_vnf_type_list = vnf_list.split(',')

        # Getting current vnf_list from database
        self.dbman.query('SELECT vnf_type FROM vnf WHERE ntw_service_id = ? AND vnf_operation = ? AND vnf_status = ?', (service_id, 'CREATE', 'COMPLETE' ))
        res = self.dbman.fetchall()

        curr_vnf_type_list = list(vnf_type['vnf_type'] for vnf_type in res)
       
        # Determining vnf to delete and to add
        add_vnf = list()
        delete_vnf = list()

        for vnf in target_vnf_type_list:
            if vnf not in curr_vnf_type_list:
                add_vnf.append(vnf.strip())

        for vnf in curr_vnf_type_list:
            if vnf not in target_vnf_type_list:
                delete_vnf.append(vnf.strip())

        self.logger.info('VNF to add to the existing Network Service: %s' % add_vnf)
        self.logger.info('VNF to delete (if adding VNF, the delete will be done after the creation): %s' % delete_vnf)

        if len(add_vnf) > 0:
            # Getting vn_group_id and max position
            self.dbman.query(
                'SELECT vn_group_id,max(vnf_position) as vnf_position FROM vnf WHERE ntw_service_id = ? AND vnf_operation = ? AND vnf_status = ?',
                (service_id, 'CREATE', 'COMPLETE'))
            result = self.dbman.fetchone()
            vn_group_id = result['vn_group_id']
            max_position = result['vnf_position']
            i = 0
            for vnf_type in add_vnf:
                i = i + 1

                # Saving temporary VNF entries into DB
                self.logger.info('Saving temporary VNFs info into DB.')

                row = (get_temp_id(), service_id, vn_group_id, vnf_type, int(max_position) + i, 'NO', 'CREATE', 'PENDING', 'NO')
                self.dbman.save_vnf(row)

                hot_package_id = '9c127b11-10e2-4148-9a67-411804c35644'  # TODO Put it in config
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

        if len(delete_vnf) > 0:
            for vnf_type in delete_vnf:
                # Getting vnf_id and vm_id to delete
                self.dbman.query('SELECT vnf_id,vm_id FROM vnf,vm WHERE vnf.ntw_service_id=? AND vnf.vnf_type=? AND vnf.vnf_id=vm.vnf_id',
                                 (service_id, vnf_type))
                result = self.dbman.fetchone()
                vnf_id = result['vnf_id']
                vm_id = result['vm_id']

                self.logger.info('Deleting VM %s' % vm_id)
                ecm_util.invoke_ecm_api(vm_id, c.ecm_service_api_vms, 'DELETE')

                self.logger.info('Waiting 40 secs to let VM remove operation to complete.')
                time.sleep(40)

                self.logger.info('Deleting VAPP %s' % vnf_id)
                ecm_util.invoke_ecm_api(vnf_id, c.ecm_service_api_vapps, 'DELETE')

    def rollback(self):
        pass




