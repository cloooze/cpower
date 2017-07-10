#!/usr/bin/env python

import sqlite3
import ecm_util as ecm_util
import nso_util as nso_util
import config as c
from event import Event
from utils import *
from ecm_exception import *


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
            custom_order_params = self.order_json['data']['order']['customOrderParams']  # check if it generates exception
        except KeyError:
            # The flow ends up here when has been sent a creteVlink as createOrder from the customworkflow since
            # the order doesn't have any customOrderParams
            pass

        #TODO check if orderstatus is COM or ERR

        #  CREATE SERVICE submitted by NSO
        create_service = get_order_items('createService', self.order_json, 1)
        create_vlink = get_order_items('createVLink', self.order_json, 1)

        if create_service is not None:
            customer_id = get_custom_order_param('Cust_Key', custom_order_params)
            rt_left = get_custom_order_param('rt-left', custom_order_params)
            rt_right = get_custom_order_param('rt-right', custom_order_params)
            rt_mgmt = get_custom_order_param('rt-mgmt', custom_order_params)
            vnf_list = get_custom_order_param('vnf_list', custom_order_params).split(',')

            operation_error = {'operation': 'createService', 'result': 'failure', 'customer-key': customer_id}
            workflow_error = {'operation': 'genericError', 'customer-key': customer_id}

            if self.order_status == 'ERR':
                self.logger.error(self.order_json['data']['order']['orderMsgs'])
                nso_util.notify_nso(operation_error)
                return 'FAILURE'

            # Checking if the needed custom order params are empty
            empty_custom_order_param = get_empty_param(customer_id=customer_id, rt_left=rt_left,
                                                       rt_right=rt_right, rt_mgmt=rt_mgmt)

            if empty_custom_order_param is not None:
                error_message = "Custom order parameter [%s] is needed but not found or empty in the request." % empty_custom_order_param
                self.logger.error(error_message)
                workflow_error['error-code'] = REQUEST_ERROR
                workflow_error['error-message'] = error_message
                nso_util.notify_nso(workflow_error)
                return 'FAILURE'

            service_id, service_name  = create_service['id'], create_service['name']

            # We got everything we need to proceed:
            # Saving customer and network service info to DB. A check is not needed as NSO should send a
            # createService only in case of first VNF creation. This means there should not be customer and service
            # already.
            try:
                self.dbman.save_customer((customer_id, customer_id + '_name'))
            except sqlite3.IntegrityError:
                # Customer already in DB, it shouldn't be possible for createService operation unless the request is re-submitted
                #after a previous request that encountered an error
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
                order_items.append(get_create_vapp(str(i), customer_id + '-' + vnf_type, c.ecm_vdc_id, 'Cpower', service_id))
                order_items.append(get_create_vm(str(i+1), c.ecm_vdc_id, customer_id + vnf_type, csr1000_image_name, vmhd_name, str(i)))
                order_items.append(get_create_vmvnic(str(i+2), vnf_type + '-left', '99', str(i+1), 'desc'))
                order_items.append(get_create_vmvnic(str(i+3), vnf_type + '-right', '100', str(i+1), 'desc'))
                #order_items.append(get_create_vmvnic(str(i+4), vnf_type + 'vnic mgmt name', '', str(i+1), 'desc', 'TODO_id_vn_mgmt'))
                i += 4 #change to 5

            order = dict(
                {
                    "tenantName": c.ecm_tenant_name,
                    "customOrderParams": [get_cop('service_id', service_id), get_cop('customer_id', customer_id)],
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
        # CREATE VLINK submitted by workflow
        elif create_vlink is not None:
            service_id = create_vlink['service']['id']
            ex_input = create_vlink['customInputParams'][0]['value']
            ex_input_s = json.loads(ex_input)
            policy_rule = ex_input_s['extensions-input']['service-instance']['si_name']

            self.dbman.query('SELECT * FROM network_service WHERE ntw_service_id=?', (service_id,))
            row = self.dbman.fetchone()
            customer_id = row['customer_id']

            operation_error = {'operation': 'createService', 'result': 'failure', 'customer-key': customer_id}
            workflow_error = {'operation': 'genericError', 'customer-key': customer_id}

            if self.order_status == 'ERR':
                self.logger.error(self.order_json['data']['order']['orderMsgs'])
                nso_util.notify_nso(operation_error)
                return 'FAILURE'

            vlink_id, vlink_name = create_vlink['id'], create_vlink['name']

            # Updating table NETWORK_SERVICE with the just created vlink_id and vlink_name
            self.dbman.query('UPDATE network_service SET vlink_id=?,vlink_name=?,ntw_policy=?  WHERE ntw_service_id=?',
                        (vlink_id, vlink_name, policy_rule, service_id))
            self.logger.info('VLink %s with id %s succesfully created.' % (vlink_name, vlink_id))
        else:
            customer_id = get_custom_order_param('customer_id', custom_order_params)
            service_id = get_custom_order_param('service_id', custom_order_params)

            if customer_id is None or service_id is None:
                self.logger.info('Received an order not handled by the Custom Workflow. Skipping execution...')
                return

            operation_error = {'operation': 'createVnf', 'result': 'failure', 'customer-key': customer_id}
            #workflow_error = {'operation': 'genericError', 'customer-key': customer_id}

            if self.order_status == 'ERR':
                self.logger.error(self.order_json['data']['order']['orderMsgs'])
                nso_util.notify_nso(operation_error)
                return 'FAILURE'

            create_vnfs = get_order_items('createVapp', self.order_json)
            create_vns = get_order_items('createVn', self.order_json)

            # Save VN_GROUP first
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
                    r = ecm_util.invoke_ecm_api(vn_id_l, c.ecm_service_api_vns, 'GET')
                    resp = json.loads(r.text)
                    vn_vimobject_id_r = resp['data']['vn']['vimObjectId']

            self.logger.info('Saving VN_GROUP info into database.')
            vn_group_row = (vn_id_l, vn_name_l, vn_vimobject_id_l, vn_id_r, vn_name_r, vn_vimobject_id_r)
            vn_group_id = self.dbman.save_vn_group(vn_group_row, False)

            for vnf in create_vnfs:
                vnf_id, vnf_name, vnf_type = vnf['id'], vnf['name'], vnf['name'].split('-')[1]

                create_vms = get_order_items('createVm', self.order_json)

                for vm in create_vms:
                    if vm['vapp']['name'] == vnf_name:
                        vm_id, vm_name = vm['id'], vm['name']

                create_vmvnics = get_order_items('createVmVnic', self.order_json)

                try:
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
                except (ECMReqStatusError, ECMConnectionError) as e:
                    self.logger.exception(e)
                    operation_error['operation'] = 'createVnf'
                    nso_util.notify_nso(operation_error)
                    return 'FAILURE'

                # Save VNF
                self.logger.info('Saving VNF info into database.')
                vnf_row = (vnf_id, service_id, vn_group_id, vnf_type, '', 'YES')
                self.dbman.save_vnf(vnf_row, False)

                # Save VM
                self.logger.info('Saving VM info into database.')
                vm_row = (vm_id, vnf_id, vm_name)
                self.dbman.save_vm(vm_row, False)

                # Save VMVNIC
                self.logger.info('Saving VMVNIC info into database.')
                vmvnic_row_l = (vmvnic_id_l, vm_id, vmvnic_name_l, vmvnic_vimobjectid_l, vmvnic_ip_l)
                vmvnic_row_r = (vmvnic_id_r, vm_id, vmvnic_name_r, vmvnic_vimobjectid_r, vmvnic_ip_r)
                self.dbman.save_vmvnic(vmvnic_row_l, False)
                self.dbman.save_vmvnic(vmvnic_row_r, False)



            self.dbman.commit()

