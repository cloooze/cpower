#!/usr/bin/env python

import ecm_util as ecm_util
import nso_util as nso_util
import config as c
from ecm_exception import *
from event import Event
from utils import *
import time


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
        """ The modifyService might be invoked by many scenarios, let's try to summarize them:
        1) NSO wants to delete a VNF, therefore it sends a modifyService with the VNF type it wants to delete
        2) Custom Workflow want's to detach a VNF from a NetworkService as it wants to delete the VNF (in this case do nothing)
        3) NSO wants to add/remove/add and remove/switch VNFs from an existing Network Service """

        modify_service = get_order_items('modifyService', self.order_json, 1)
        service_id = modify_service['id']

        modify_service_cip = get_custom_input_params('modifyService', self.order_json)

        if get_custom_input_param('next_action', modify_service_cip) == 'skip':
            self.logger.info('Nothing to do.')
            return

        # Getting customer_id, it will be used later
        self.dbman.query('SELECT customer_id FROM network_service WHERE ntw_service_id = ?', (service_id,))
        customer_id = self.dbman.fetchone()['customer_id']

        # Getting target vnf_list
        target_vnf_type_list = get_custom_input_param('vnf_list', modify_service_cip).split(',')

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
        self.logger.info('VNF to delete (will be deleted if the creation succeed): %s' % delete_vnf)

        if len(add_vnf) > 0:
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
                order_items.append(get_create_vmvnic(str(i + 4), customer_id + '-' + vnf_type + '-mgmt', '', str(i + 1), 'desc', c.mgmt_vn_id))
                i += 5

                # Saving temporary VNFs to ADD into DB
                self.logger.info('Saving temporary VNF [%s] to ADD into database' % vnf_type)
                row = (customer_id + vnf_type + '_' + get_temp_id(), service_id, '', vnf_type, target_vnf_type_list.index(vnf_type) + 1, 'NO', 'CREATE', 'PENDING')
                self.dbman.save_vnf(row)

            order = dict(
                {
                    "tenantName": c.ecm_tenant_name,
                    "customOrderParams": [
                        get_cop('service_id', service_id),
                        get_cop('customer_id', customer_id)
                    ],
                    "orderItems": order_items
                }
            )

            if len(delete_vnf) > 0:
                order['customOrderParams'].append(get_cop('next_action','delete_vnf'))
                order['customOrderParams'].append(get_cop('vnf_list', ','.join(vnf for vnf in delete_vnf)))
                # Saving temporary VNFs to ADD into DB
                for vnf_type in delete_vnf:
                    self.logger.info('Saving temporary VNF [%s] to DELETE into database' % vnf_type)
                    self.dbman.query('UPDATE vnf SET vnf_operation = ?, vnf_status = ? WHERE vnf_type = ? AND vnf_operation = ? AND vnf_status = ? AND ntw_service_id = ?', ('DELETE', 'PENDING', vnf_type, 'CREATE', 'COMPLETE', service_id))

            ecm_util.invoke_ecm_api(None, c.ecm_service_api_orders, 'POST', order)

        elif len(delete_vnf) > 0:  # Doing the delete here ONLY if there is nothing to add
            placeholders = ','.join('?' for vnf in delete_vnf)

            self.dbman.query('SELECT vnf_id FROM vnf WHERE ntw_service_id = ? AND vnf_type IN (%s)' % placeholders,
                             tuple([service_id]) + tuple(delete_vnf))
            res = self.dbman.fetchall()

            if res is not None:
                for vnf in res:
                    vnf_id = vnf['vnf_id']
                    self.dbman.query('UPDATE vnf SET vnf_operation = ?, vnf_status = ? WHERE vnf_id = ?', ('DELETE', 'PENDING', vnf_id))
                    ecm_util.invoke_ecm_api(vnf_id, c.ecm_service_api_vapps, 'DELETE')

    def rollback(self):
        pass




