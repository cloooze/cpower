#!/usr/bin/env python

from event import Event
import nso_util
from utils import *

INTERNAL_ERROR = '100'
REQUEST_ERROR = '200'
NETWORK_ERROR = '300'


class DeleteVnf(Event):

    def __init__(self, order_status, order_id, source_api, order_json):
        super(DeleteVnf, self).__init__()

        self.order_json = order_json
        self.order_status = order_status
        self.order_id = order_id
        self.source_api = source_api

    def notify(self):
        vnf_id = get_order_items('deleteVapp', self.order_json, 1).fetchone()['id']

        res = self.dbman.query('SELECT * FROM vnf WHERE vnf_id = ? AND vnf_operation = ?', (vnf_id, 'ROLLBACK')).fetchall()

        if res is None:
            res = self.dbman.query('SELECT network_service.customer_id, network_service.ntw_service_id, vnf.vnf_type '
                                   'FROM vnf, network_service '
                                   'WHERE vnf.vnf_id = ? '
                                   'AND vnf.ntw_service_id = network_service.ntw_service_id', (vnf_id,)).fetchone()

            customer_id = res['customer_id']
            service_id = res['ntw_service_id']
            vnf_name = res['vnf_type']

            if self.order_status == 'ERR':
                nso_util.notify_nso('deleteVnf', nso_util.get_delete_vnf_data_response('failed', customer_id))
            else:
                nso_util.notify_nso('deleteVnf', nso_util.get_delete_vnf_data_response('success', customer_id, service_id, vnf_id, vnf_name))

    def execute(self):
        if self.order_status == 'ERR':
            return 'FAILURE'

        delete_vnf = get_order_items('deleteVapp', self.order_json, 1)

        vnf_id = delete_vnf['id']

        self.dbman.query('SELECT ns.ntw_policy,vnf.vnf_type, vnf.ntw_service_id '
                         'FROM network_service ns, vnf '
                         'WHERE vnf.vnf_id = ? '
                         'AND vnf.ntw_service_id = ns.ntw_service_id', (vnf_id,))

        res = self.dbman.fetchone()

        if res is None:
            self.logger.info('The event is not generated by supported system, skipping execution.')
            return

        # Doing this because ntw_policy column contains comma separated values as --> <cust_id>-<vnf_type>
        ntw_policy = res['ntw_policy']
        vnf_type = res['vnf_type']
        service_id = res['ntw_service_id']

        ntw_policy = list(vnf for vnf in ntw_policy if vnf_type not in vnf)

        self.dbman.query('UPDATE network_service SET ntw_policy = ? WHERE ntw_service_id = ?', tuple(ntw_policy) + tuple([service_id]))
        self.logger.info('Updating NTW_POLICY %s from database.' % ntw_policy)

        self.dbman.query('UPDATE vnf SET vnf.vnf_status = ? WHERE vnf_id = ?', ('COMPLETE', vnf_id))
        self.logger.info('Updating VNF_OPERATION column from VNF table')

        self.dbman.commit()

