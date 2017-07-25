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


class DeleteService(Event):
    def __init__(self, order_status, order_id, source_api, order_json):
        super(DeleteService, self).__init__()

        self.order_json = order_json
        self.order_status = order_status
        self.order_id = order_id
        self.source_api = source_api

    def notify(self):
        service_id = self.event_params['service_id']
        customer_id = self.event_params['customer_id']

        if self.order_status == 'ERR':
            nso_util.notify_nso('deleteService', nso_util.get_delete_service_data_response('failed', customer_id, service_id))
        else:
            nso_util.notify_nso('deleteService', nso_util.get_delete_service_data_response('success', customer_id, service_id))

    def execute(self):
        if self.order_status == 'ERR':
            return 'FAILURE'

        delete_service = get_order_items('deleteService', self.order_json, 1)
        service_id = delete_service['id']

        self.logger.info('Network service [%s] succesfully deleted. Deleting associated VNs...' % service_id)

        self.dbman.query('SELECT customer_id FROM network_service ns WHERE ns.ntw_service_id=?', (service_id,))
        row = self.dbman.fetchone()

        if not row:
            self.logger.info('No VNs associated to Network Service [%s].' % service_id)
            return

        customer_id = row['customer_id']

        self.event_params = {'customer_id': customer_id, 'service_id': service_id}

        self.dbman.query('SELECT vn_left_id, vn_right_id FROM network_service ns, vnf, vn_group vn WHERE '
                         'ns.ntw_service_id=? and ns.ntw_service_id=vnf.ntw_service_id and vn.vnf_id=vnf.vnf_id',
                         (service_id,))
        row = self.dbman.fetchone()

        vn_left_id, vn_right_id = row['vn_left_id'], row['vn_right_id']

        ecm_util.invoke_ecm_api(vn_left_id, c.ecm_service_api_vns, 'DELETE')
        ecm_util.invoke_ecm_api(vn_right_id, c.ecm_service_api_vns, 'DELETE')
