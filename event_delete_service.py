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


class DeleteService(EventManager):
    def __init__(self, order_status, order_id, source_api, order_json):
        super(DeleteService, self).__init__()

        self.order_json = order_json
        self.order_status = order_status
        self.order_id = order_id
        self.source_api = source_api

    def notify(self):
        pass

    def execute(self):
        workflow_error = {'operation': 'genericError', 'customer-key': ''}

        if self.order_status == 'ERR':
            self.logger.error(self.order_json['data']['order']['orderMsgs'])
            nso_util.notify_nso(workflow_error)
            return 'FAILURE'

        delete_service = get_order_items('deleteService', self.order_json, 1)
        service_id = delete_service['id']

        self.logger.info('Network service [%s] succesfully deleted. Deleting associated VNs...' % service_id)

        self.dbman.query('SELECT customer_id FROM network_service ns WHERE ns.ntw_service_id=?', (service_id,))
        row = self.dbman.fetchone()
        customer_id = row['customer_id']

        operation_error = {'operation': 'deleteService', 'result': 'failure', 'customer-key': customer_id}

        self.dbman.query('SELECT vn_left_id, vn_right_id FROM network_service ns, vnf, vn_group vn WHERE '
                         'ns.ntw_service_id=? and ns.ntw_service_id=vnf.ntw_service_id and vn.vnf_id=vnf.vnf_id',
                         (service_id,))
        row = self.dbman.fetchone()

        vn_left_id, vn_right_id = row['vn_left_id'], row['vn_right_id']

        try:
            ecm_util.invoke_ecm_api(vn_left_id, c.ecm_service_api_vns, 'DELETE')
            ecm_util.invoke_ecm_api(vn_right_id, c.ecm_service_api_vns, 'DELETE')
        except (ECMReqStatusError, ECMConnectionError) as e:
            self.logger.exception(e)
            nso_util.notify_nso(workflow_error)
            return 'FAILURE'
