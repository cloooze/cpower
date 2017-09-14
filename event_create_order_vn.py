#!/usr/bin/env python

import sqlite3
import ecm_util as ecm_util
import nso_util as nso_util
import config as c
from event import Event
from utils import *
from ecm_exception import *
import time


class CreateOrderVn(Event):
    def __init__(self, order_status, order_id, source_api, order_json):
        super(CreateOrderVn, self).__init__()

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

        customer_id = get_custom_order_param('customer_id', custom_order_params)
        service_id = get_custom_order_param('service_id', custom_order_params)
        vnf_type_list = get_custom_order_param('vnf_type_list', custom_order_params)

        # Getting createVn from order result (x2 left-right)
        create_vn_list = get_order_items('createVn', self.order_json)

        for create_vn in create_vn_list:
            vn_id = create_vn['id']
            vn_name = create_vn['name']

            r = ecm_util.invoke_ecm_api(vn_id, c.ecm_service_api_vns, 'GET')
            resp = json.loads(r.text)

            vn_vimobject_id = resp['data']['vn']['vimObjectId']

            if 'left' in vn_name: vn_left_row = (vn_id, vn_name, vn_vimobject_id)
            if 'right' in vn_name: vn_right_row = (vn_id, vn_name, vn_vimobject_id)

        # Saving VN info into DB
        self.logger.info('Saving VNs info into DB.')
        vn_row = vn_left_row + vn_right_row
        vn_group_id = self.dbman.save_vn_group(vn_row, True)

        # DEPLOY HOT PACKAGE HERE
        hot_package_id = c.hot_package_id # TODO Put it in config
        hot_file_json = load_json_file('./json/deploy_hot_package.json')

        # Preparing the Hot file
        vnf_type = vnf_type_list.split(',')[0]

        hot_file_json['tenantName'] = c.ecm_tenant_name
        hot_file_json['vdc']['id'] = c.ecm_vdc_id
        hot_file_json['hotPackage']['vapp']['name'] = vnf_type + '-' + customer_id
        hot_file_json['hotPackage']['vapp']['configData'][0]['value'] = vnf_type + '-' + customer_id
        hot_file_json['hotPackage']['vapp']['configData'][1]['value'] = customer_id + '-left'
        hot_file_json['hotPackage']['vapp']['configData'][2]['value'] = customer_id + '-right'
        hot_file_json['hotPackage']['vapp']['configData'][3]['value'] = c.mgmt_vn_name

        # Saving temporary VNF entries into DB
        self.logger.info('Saving temporary VNFs info into DB.')
        i = 1
        for vnf_type in vnf_type_list.split(','):
            row = (get_temp_id(), service_id, vn_group_id, vnf_type, i, 'NO', 'CREATE', 'PENDING', 'NO')
            self.dbman.save_vnf(row)
            i += 1

        self.logger.info('Depolying HOT package %s' % hot_package_id)
        ecm_util.deploy_hot_package(hot_package_id, hot_file_json)

    def rollback(self):
        pass
