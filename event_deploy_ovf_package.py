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


class DeployOvfPackage(EventManager):

    def __init__(self, order_status, order_id, source_api, order_json):
        super(DeployOvfPackage, self).__init__()

        self.order_json = order_json
        self.order_status = order_status
        self.order_id = order_id
        self.source_api = source_api

    def notify(self):
        pass

    def execute(self):
        # OVF structure 1 createVapp, 1 createVm, 3 createVmVnic, 0/2 createVn
        create_vm = get_order_items('createVm', self.order_json)[0]
        create_vapp = get_order_items('createVapp', self.order_json)[0]
        create_vns = get_order_items('createVn', self.order_json)
        create_vmvnics = get_order_items('createVmVnic', self.order_json)

        customer_id = create_vm['name'].split('-')[0]

        operation_error = {'operation': 'createVnf', 'result': 'failure', 'customer-key': customer_id}
        workflow_error = {'operation': 'genericError', 'customer-key': customer_id}

        if self.order_status == 'ERR':
            self.logger.error(self.order_json['data']['order']['orderMsgs'])
            nso_util.notify_nso(operation_error)
            return 'FAILURE'

            self.logger.info('OVF Package succesfully deployed.')

        # Getting VNF, VNs, VMVNICS detail
        vnf_id = create_vapp['id']
        vm_id, vm_name = create_vm['id'], create_vm['name']

        if create_vns is not None:
            for vn in create_vns:
                if 'left' in vn['name']:
                    vn_left = vn
                elif 'right' in vn['name']:
                    vn_right = vn

        vmvnic_ids, vmvnic_names = list(), list()

        for vmvnic in create_vmvnics:
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
            resp = ecm_util.invoke_ecm_api(vn_left['id'], c.ecm_service_api_vns, 'GET')
            vn_left_resp_json = json.loads(resp.text)

            resp = ecm_util.invoke_ecm_api(vn_right['id'], c.ecm_service_api_vns, 'GET')
            vn_right_resp_json = json.loads(resp.text)
        except (ECMReqStatusError, ECMConnectionError) as e:
            self.logger.exception(e)
            nso_util.notify_nso(operation_error)
            return 'FAILURE'

        vn_group_row = (vnf_id, vn_left['id'], vn_left['name'], vn_left_resp_json['data']['vn']['vimObjectId'],
                        vn_right['id'], vn_right['name'], vn_right_resp_json['data']['vn']['vimObjectId'])
        vnf_row = (vnf_id, service_id, vnf_type, '1', 'NO')
        vm_row = (vm_id, vnf_id, vm_name, vmvnic_ids[0], vmvnic_names[0], '', vmvnic_ids[1], vmvnic_names[1], '')

        try:
            self.dbman.save_vn_group(vn_group_row, False)
            self.dbman.save_vnf(vnf_row, False)
            self.dbman.save_vm(vm_row, False)
        except sqlite3.IntegrityError:
            self.logger.exception('Something went wrong during storing data into database.')
            self.dbman.rollback()
            # TODO notify NSO
            return 'FAILURE'

        dbman.commit()

        self.logger.info('Information related to the deployed OVF saved into database.')
        self.logger.info('Associating Network Service to VNF...')

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



