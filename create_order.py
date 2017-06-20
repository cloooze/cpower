#!/usr/bin/env python

import sqlite3
import logging.config
import ecm_util as ecm_util
import nso_util as nso_util
from db_manager import DBManager
from ecm_exception import *
from nso_exception import *
import config as c
from order_manager import OrderManager

logger = logging.getLogger('cpower')

INTERNAL_ERROR = '100'
REQUEST_ERROR = '200'
NETWORK_ERROR = '300'

class CreateOrder(OrderManager):

    def __init__(self, order_status, order_id, source_api, order_json):
        self.order_json = order_json
        self.order_status = order_status
        self.order_id = order_id
        self.source_api = source_api
        self.dbman = DBManager()

    def execute(self):
        # Getting customer order params from getOrder response
        create_order_cop = dict()
        try:
            create_order_cop = self.order_json['data']['order']['customOrderParams']  # check if it generates exception
        except KeyError:
            # The flow ends up here when has been sent a creteVlink as createOrder from the customworkflow since
            # the order doesn't have any customOrderParams
            pass

        # Checking if order type is createService
        if self.get_order_items('createService', self.order_json) is not None:
            customer_id = self.get_custom_order_param('Cust_Key', create_order_cop)
            vnf_type = self.get_custom_order_param('vnf_type', create_order_cop)
            rt_left = self.get_custom_order_param('rt-left', create_order_cop)
            rt_right = self.get_custom_order_param('rt-right', create_order_cop)
            rt_mgmt = self.get_custom_order_param('rt-mgmt', create_order_cop)

            operation_error = {'operation': 'createService', 'result': 'failure', 'customer-key': customer_id}
            workflow_error = {'operation': 'genericError', 'customer-key': customer_id}

            if self.order_status == 'ERR':
                logger.error(self.order_json['data']['order']['orderMsgs'])
                nso_util.notify_nso(operation_error)
                super.exit('FAILURE')

            # Checking if the needed custom order params are empty
            empty_cop = self.get_empty_param(customer_id=customer_id, vnf_type=vnf_type, rt_left=rt_left,
                                        rt_right=rt_right,
                                        rt_mgmt=rt_mgmt)

            if empty_cop is not None:
                error_message = "Custom order parameter '%s' not found or empty." % empty_cop
                logger.error(error_message)
                workflow_error['error-code'] = REQUEST_ERROR
                workflow_error['error-message'] = error_message
                nso_util.notify_nso(workflow_error)
                super.exit('FAILURE')

            service_id = self.get_order_items('createService', self.order_json)[0]['id']
            service_name = self.get_order_items('createService', self.order_json)[0]['name']

            # We got everything we need to proceed:
            # Saving customer and network service info to DB. A check is not needed as NSO should send a
            # createService only in case of first VNF creation. This means there should not be customer and service
            # already.
            try:
                self.dbman.save_customer((customer_id, customer_id + '_name'))
            except sqlite3.IntegrityError:
                # Customer already in DB, it shouldn't be possible for createService operation
                pass

            ntw_service_row = (
                service_id, customer_id, service_name, rt_left, rt_right, rt_mgmt, vnf_type, '', '', '')
            self.dbman.save_network_service(ntw_service_row)
            logger.info('Network Service \'%s\' successfully stored to DB.' % service_id)

            # Loading the right ovf package id depending on the requested VNF type.
            # It is loaded the ovf package 1 as we are in the 'createService' (meaning that the first VNF for the
            # service is being requested
            try:
                ovf_package_id = self.get_ovf_package_id(vnf_type, 'create')
            except VnfTypeException:
                error_message = 'VNF Type \'%s\' is not supported.' % vnf_type
                logger.error(error_message)
                workflow_error['error-code'] = REQUEST_ERROR
                workflow_error['error-message'] = error_message
                nso_util.notify_nso(workflow_error)
                super.exit('FAILURE')

            deploy_ovf_package_file = './json/deploy_ovf_package.json'
            ovf_package_json = self.load_json_file(deploy_ovf_package_file)
            ovf_package_json['tenantName'] = c.ecm_tenant_name
            ovf_package_json['vdc']['id'] = c.ecm_vdc_id
            ovf_package_json['ovfPackage']['namePrefix'] = customer_id + '-'

            logger.info('Deploying OVF Package %s' % ovf_package_id)
            try:
                ecm_util.deploy_ovf_package(ovf_package_id, ovf_package_json)
            except (ECMReqStatusError, ECMConnectionError) as e:
                logger.exception(e)
                operation_error['operation'] = 'createVnf'
                nso_util.notify_nso(operation_error)
                super.exit('FAILURE')

        elif self.get_order_items('createVLink', self.order_json) is not None:
            create_vlink = self.get_order_items('createVLink', self.order_json)[0]
            service_id = create_vlink['service']['id']
            policy_name = create_vlink['name'].split('-')[0] + '_' + create_vlink['name'].split('-')[2]

            self.dbman.query('SELECT * FROM network_service WHERE ntw_service_id=?', (service_id,))
            row = self.dbman.fetchone()
            customer_id = row['customer_id']

            operation_error = {'operation': 'createService', 'result': 'failure', 'customer-key': customer_id}
            workflow_error = {'operation': 'genericError', 'customer-key': customer_id}

            if self.order_status == 'ERR':
                logger.error(self.order_json['data']['order']['orderMsgs'])
                nso_util.notify_nso(operation_error)
                super.exit('FAILURE')

            vlink_id = create_vlink['id']
            vlink_name = create_vlink['name']

            # Updating table NETWORK_SERVICE with the just created vlink_id and vlink_name
            self.dbman.query('UPDATE network_service SET vlink_id=?,vlink_name=?,ntw_policy=?  WHERE ntw_service_id=?',
                        (vlink_id, vlink_name, policy_name, service_id))
            logger.info('VLink %s with id %s succesfully created.' % (vlink_name, vlink_id))
        else:
            logger.error('Custmor workflow ended up in a inconsistent state, please check the logs.')
            super.exit('FAILURE')