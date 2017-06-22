#!/usr/bin/env python

import sqlite3
import ecm_util as ecm_util
import nso_util as nso_util
import config as c
from event_manager import EventManager
from utils import *
from ecm_exception import *


INTERNAL_ERROR = '100'
REQUEST_ERROR = '200'
NETWORK_ERROR = '300'


class CreateOrder(EventManager):

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

        #######################
        #  CREATE SERVICE     #
        #######################
        create_service = get_order_items('createService', self.order_json, 1)
        create_vlink = get_order_items('createVLink', self.order_json, 1)

        if create_service is not None:
            customer_id = get_custom_order_param('Cust_Key', custom_order_params)
            vnf_type = get_custom_order_param('vnf_type', custom_order_params)
            rt_left = get_custom_order_param('rt-left', custom_order_params)
            rt_right = get_custom_order_param('rt-right', custom_order_params)
            rt_mgmt = get_custom_order_param('rt-mgmt', custom_order_params)

            operation_error = {'operation': 'createService', 'result': 'failure', 'customer-key': customer_id}
            workflow_error = {'operation': 'genericError', 'customer-key': customer_id}

            if self.order_status == 'ERR':
                self.logger.error(self.order_json['data']['order']['orderMsgs'])
                nso_util.notify_nso(operation_error)
                return 'FAILURE'

            # Checking if the needed custom order params are empty
            empty_custom_order_param = get_empty_param(customer_id=customer_id, vnf_type=vnf_type, rt_left=rt_left,
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
                # Customer already in DB, it shouldn't be possible for createService operation
                pass

            ntw_service_row = (service_id, customer_id, service_name, rt_left, rt_right, rt_mgmt, vnf_type, '', '', '')
            self.dbman.save_network_service(ntw_service_row)
            self.logger.info('Network Service \'%s\' successfully stored to DB.' % service_id)

            try:
                ovf_package_id = get_ovf_package_id(vnf_type, 'create')
            except VnfTypeException:
                error_message = "VNF Type '%s' is not supported." % vnf_type
                self.logger.error(error_message)
                workflow_error['error-code'] = REQUEST_ERROR
                workflow_error['error-message'] = error_message
                nso_util.notify_nso(workflow_error)
                return 'FAILURE'

            ovf_package_file = './json/deploy_ovf_package.json'
            ovf_package_json = load_json_file(ovf_package_file)
            ovf_package_json['tenantName'] = c.ecm_tenant_name
            ovf_package_json['vdc']['id'] = c.ecm_vdc_id
            ovf_package_json['ovfPackage']['namePrefix'] = customer_id + '-'

            self.logger.info('Deploying OVF Package %s' % ovf_package_id)

            try:
                ecm_util.deploy_ovf_package(ovf_package_id, ovf_package_json)
            except (ECMReqStatusError, ECMConnectionError) as e:
                self.logger.exception(e)
                operation_error['operation'] = 'createVnf'
                nso_util.notify_nso(operation_error)
                return 'FAILURE'

        #######################
        #  CREATE VLINK       #
        #######################
        elif create_vlink is not None:
            service_id = create_vlink['service']['id']
            policy_name = create_vlink['name'].split('-')[0] + '_' + create_vlink['name'].split('-')[2]
            # Fix this, the name is composed customer <customer_id>-SDN-policy, the customer_my might contain a - ?

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
                        (vlink_id, vlink_name, policy_name, service_id))
            self.logger.info('VLink %s with id %s succesfully created.' % (vlink_name, vlink_id))
        else:
            self.logger.info('Received a [createOrder] request but neither [createService] nor [createVLink] order items in it.')

