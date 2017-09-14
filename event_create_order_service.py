#!/usr/bin/env python

import sqlite3
import ecm_util as ecm_util
import nso_util as nso_util
import config as c
from event import Event
from utils import *
from ecm_exception import *
import time

INTERNAL_ERROR = '100'
REQUEST_ERROR = '200'
NETWORK_ERROR = '300'


class CreateOrderService(Event):
    def __init__(self, order_status, order_id, source_api, order_json):
        super(CreateOrderService, self).__init__()

        self.order_json = order_json
        self.order_status = order_status
        self.order_id = order_id
        self.source_api = source_api

    def notify(self):
        if self.order_status == 'ERR':
            try:
                custom_order_params = self.order_json['data']['order']['customOrderParams']
                customer_id = get_custom_order_param('customer_id', custom_order_params)
            except KeyError:
                self.logger.info('Received a request not handled by custom workflow. Skipping execution')
                return

            nso_util.notify_nso('createService', nso_util.get_create_vnf_data_response('failed', customer_id))

    def execute(self):
        if self.order_status == 'ERR':
            return 'FAILURE'

        # Getting customer order params from getOrder response
        custom_order_params = dict()
        try:
            custom_order_params = self.order_json['data']['order']['customOrderParams']  # check if it throws exception
        except KeyError:
            # The flow ends up here when has been sent a creteVlink as createOrder from the customworkflow since
            # the order doesn't have any customOrderParams
            pass

        # CREATE SERVICE submitted by NSO
        create_service = get_order_items('createService', self.order_json, 1)

        # Processing post-createService (sub by NSO)
        customer_id = get_custom_order_param('customer_key', custom_order_params)
        rt_left = get_custom_order_param('rt_left', custom_order_params)
        rt_right = get_custom_order_param('rt_right', custom_order_params)
        rt_mgmt = get_custom_order_param('rt_mgmt', custom_order_params)
        vnf_type_list = get_custom_order_param('vnf_list', custom_order_params)

        # Checking if the needed custom order params are empty
        empty_custom_order_param = get_empty_param(customer_id=customer_id, rt_left=rt_left, rt_right=rt_right,
                                                   vnf_list=vnf_type_list)

        if empty_custom_order_param is not None:
            # Notifying here because order_status is COM
            self.logger.error("Create Service order is missing mandatory custom order parameters.")
            nso_util.notify_nso('createService', nso_util.get_create_vnf_data_response('failed', customer_id))
            return 'FAILURE'

        service_id, service_name = create_service['id'], create_service['name']

        # We got all we need to proceed:
        # Saving customer and network service info to DB. A check is not needed as NSO should send a
        # createService only in case of first VNF creation. This means there should not be customer and service
        # already into DB.
        try:
            self.dbman.save_customer((customer_id, customer_id + '_name'))
        except sqlite3.IntegrityError:
            # Customer already in DB, it shouldn't be possible for createService operation unless the request is
            # re-submitted after a previous request that encountered an error
            pass

        ntw_service_row = (service_id, customer_id, service_name, rt_left, rt_right, rt_mgmt, '', '', '', 'NO')
        try:
            self.dbman.save_network_service(ntw_service_row)
            self.logger.info('Network Service [%s] successfully stored into database.' % service_id)
        except sqlite3.IntegrityError:
            # Same as for customer
            pass

        # Create order - create VNs

        order_items = list()
        order_items.append(get_create_vn('1', c.ecm_vdc_id, customer_id + '-left', 'Virtual Network left'))
        order_items.append(get_create_vn('2', c.ecm_vdc_id, customer_id + '-right', 'Virtual Network right'))

        order = dict(
            {
                "tenantName": c.ecm_tenant_name,
                "customOrderParams": [get_cop('customer_id', customer_id),
                                      get_cop('service_id', service_id),
                                      get_cop('vnf_type_list', vnf_type_list)],
                "orderItems": order_items
            }
        )

        ecm_util.invoke_ecm_api(None, c.ecm_service_api_orders, 'POST', order)

    def rollback(self):
        pass
