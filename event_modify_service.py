#!/usr/bin/env python

import ecm_util as ecm_util
import nso_util as nso_util
import config as c
from ecm_exception import *
from event import Event
from utils import *


INTERNAL_ERROR = '100'
REQUEST_ERROR = '200'
NETWORK_ERROR = '300'


class ModifyService(Event):

    def __init__(self, order_status, order_id, source_api, order_json):
        super(ModifyService, self).__init__()

        self.order_json = order_json
        self.order_status = order_status
        self.order_id = order_id
        self.source_api = source_api

    def notify(self):
        pass

    def execute(self):
        modify_service = get_order_items('modifyService', self.order_json, 1)
        service_id = modify_service['id']

        modify_service_cip = get_custom_input_params('modifyService', self.order_json)

        if get_custom_input_param('next_action', modify_service_cip) == 'skip':
            self.logger.info('Nothing to do.')
            return

        customer_id = get_custom_input_param('Cust_Key', modify_service_cip)

        if not customer_id:
            self.logger.info('Nothing to do.')
            return

        operation_error = {'operation': 'createService', 'result': 'failure', 'customer-key': customer_id}
        workflow_error = {'operation': 'genericError', 'customer-key': customer_id}

        if self.order_status == 'ERR':
            self.logger.error(self.order_json['data']['order']['orderMsgs'])
            nso_util.notify_nso(operation_error)
            return 'FAILURE'

        # Getting target vnf_list
        target_vnf_type_list = get_custom_input_param('vnf_list', modify_service_cip).split(',')

        # Getting current vnf_list from database
        self.dbman.query('SELECT vnf_type FROM vnf WHERE ntw_service_id = ?', (service_id, ))
        res = self.dbman.fetchall()

        curr_vnf_type_list = list()
        for vnf_type in res:
            curr_vnf_type_list.append(vnf_type['vnf_type'])

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
        self.logger.info('VNF to delete to the existing Network Service: %s' % delete_vnf)

        # Sending order for new vnf to create
        order_items = list()

        csr1000_image_name = 'csr1000v-universalk9.16.04.01'
        fortinet_image_name = 'todo'
        vmhd_name = '2vcpu_4096MBmem_40GBdisk'

        # Getting existing VN_LFT_ID and VN_RIGHT_ID for this network service
        self.dbman.query('SELECT vn_left_id, vn_right_id '
                         'FROM vnf, vn_group '
                         'WHERE vnf.ntw_service_id = ? '
                         'AND vnf.vn_group_id = vn_group.vn_group_id', (service_id, ))
        res = self.dbman.fetchone()
        vn_left_id = res['vn_left_id']
        vn_right_id = res['vn_right_id']

        i = 1
        for vnf_type in add_vnf:
            order_items.append(get_create_vapp(str(i), customer_id + '-' + vnf_type, c.ecm_vdc_id, 'Cpower', service_id))
            order_items.append(get_create_vm(str(i + 1), c.ecm_vdc_id, customer_id + vnf_type, csr1000_image_name, vmhd_name, str(i)))
            order_items.append(get_create_vmvnic(str(i + 2), customer_id + '-' + vnf_type + '-left', '', str(i + 1), 'desc', vn_left_id))
            order_items.append(get_create_vmvnic(str(i + 3), customer_id + '-' + vnf_type + '-right', '', str(i + 1), 'desc', vn_right_id))
            # order_items.append(get_create_vmvnic(str(i+4), customer_id + '-' + vnf_type + '-mgmt', '', str(i+1), 'desc', c.mgmt_vn_id))
            i += 4  # TODO change to 5 uncomment

        order = dict(
            {
                "tenantName": c.ecm_tenant_name,
                "customOrderParams": [get_cop('service_id', service_id), get_cop('customer_id', customer_id),
                                      get_cop('next_action','delete_vnf'), get_cop('vnf_list', ','.join(vnf for vnf in delete_vnf))],
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

        # TODO send modifyService with ex-input

        '''
        self.logger.info('Modify VLINK object...')

        vlink_json = load_json_file('json/create_vlink.json')
        vlink_json['orderItems'][0]['createVLink']['name'] = customer_id + '-SDN-policy'
        vlink_json['orderItems'][0]['createVLink']['service']['id'] = service_id

        ex_input = load_json_file('json/extensions_input_create.json')

        # In case of multiple VNF, duplicate the entire service-instance tag
        policy_rule_list = list()
        '''


