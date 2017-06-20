#!/usr/bin/env python

import logging.config
import ecm_util as ecm_util
import nso_util as nso_util
from db_manager import DBManager
from ecm_exception import *
import config as c
from event_manager import OrderManager


INTERNAL_ERROR = '100'
REQUEST_ERROR = '200'
NETWORK_ERROR = '300'


class DeployOvfPackage(OrderManager):

    def __init__(self, order_status, order_id, source_api, order_json):
        self.order_json = order_json
        self.order_status = order_status
        self.order_id = order_id
        self.source_api = source_api

        self.dbman = DBManager()
        self.logger = logging.getLogger('cpower')

    def notify(self):
        pass

    def execute(self):
        # OVF structure 1 createVapp, 1 createVm, 3 createVmVnic, 0/2 createVn
        customer_id = self.get_order_items('createVm', self.order_json)[0]['name'].split('-')[0]

        operation_error = {'operation': 'createVnf', 'result': 'failure', 'customer-key': customer_id}
        workflow_error = {'operation': 'genericError', 'customer-key': customer_id}

        if self.order_status == 'ERR':
            self.logger.error(self.order_json['data']['order']['orderMsgs'])
            nso_util.notify_nso(operation_error)
            return 'FAILURE'

            self.logger.info('OVF Package succesfully deployed.')

        # Getting VNF, VNs, VMVNICS detail
        vnf_id = self.get_order_items('createVapp', self.order_json)[0]['id']
        vm_id = self.get_order_items('createVm', self.order_json)[0]['id']
        vm_name = self.get_order_items('createVm', self.order_json)[0]['name']

        vns = self.get_order_items('createVn', order_json)
        if vns is not None:
            for vn in vns:
                if 'left' in vn['name']:
                    vn_left = vn
                elif 'right' in vn['name']:
                    vn_right = vn

        vmvnics = self.get_order_items('createVmVnic', order_json)
        vmvnic_ids = []
        vmvnic_names = []
        for vmvnic in vmvnics:
            if 'mgmt' not in vmvnic['name'] and 'management' not in vmvnic['name']:
                vmvnic_ids.append(vmvnic['id'])
                vmvnic_names.append(vmvnic['name'])

        # Getting ntw service id and vnftype for this customer (assuming that 1 customer can have max 1 ntw service)
        self.dbman.query('SELECT ntw_service_id, vnf_type FROM network_service ns WHERE ns.customer_id = ?',
                    (customer_id,))
        row = self.dbman.fetchone()
        service_id = row['ntw_service_id']
        vnf_type = row['vnf_type']  # ???

        # Checking if there is already a VNF for this network service
        self.dbman.query('SELECT * FROM vnf WHERE ntw_service_id=?', (service_id,))
        row = self.dbman.fetchone()
        existing_vnf_id = None
        if row is not None:
            # Move vnf_position to 2
            self.dbman.query('UPDATE vnf SET vnf_position=? WHERE vnf.ntw_service_id=?', ('2', service_id), False)
            existing_vnf_id = row['vnf_id']

        try:
            # Saving VN group info to db
            vn_left_resp = ecm_util.invoke_ecm_api(vn_left['id'], c.ecm_service_api_vns, 'GET')
            vn_left_resp_json = json.loads(vn_left_resp.text)

            vn_right_resp = ecm_util.invoke_ecm_api(vn_right['id'], c.ecm_service_api_vns, 'GET')
            vn_right_resp_json = json.loads(vn_right_resp.text)
        except (ECMReqStatusError, ECMConnectionError) as e:
            self.logger.exception(e)
            nso_util.notify_nso(operation_error)
            return 'FAILURE'

        vn_group_row = (vnf_id, vn_left['id'], vn_left['name'], vn_left_resp_json['data']['vn']['vimObjectId'],
                        vn_right['id'], vn_right['name'], vn_right_resp_json['data']['vn']['vimObjectId'])

        self.dbman.save_vn_group(vn_group_row, False)

        # Saving VNF info to db
        vnf_row = (vnf_id, service_id, vnf_type, '1', 'NO')
        self.dbman.save_vnf(vnf_row, False)

        # Saving VM info to db
        vm_row = (vm_id, vnf_id, vm_name, vmvnic_ids[0], vmvnic_names[0], '', vmvnic_ids[1], vmvnic_names[1], '')
        self.dbman.save_vm(vm_row, False)

        self.logger.info('Information related to OVF Package saved into DB.')
        self.logger.info('Associating Network Service to VNF...')

        # Modifying service
        modify_service_file = './json/modify_service.json'
        modify_service_json = load_json_file(modify_service_file)
        modify_service_json['vapps'][0]['id'] = vnf_id
        modify_service_json['customInputParams'].append({"tag": "Cust_Key", "value": customer_id})
        if existing_vnf_id is not None:
            modify_service_json['vapps'].append({"id": existing_vnf_id})

        try:
            ecm_util.invoke_ecm_api(service_id, c.ecm_service_api_services, 'PUT', modify_service_json)
        except (ECMReqStatusError, ECMConnectionError) as e:
            logger.exception(e)
            operation_error['operation'] = 'createVnf'
            nso_util.notify_nso(operation_error)
            return 'FAILURE'

        dbman.commit()
        return 'SUCCESS'
