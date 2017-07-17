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
        pass

    def execute(self):
        workflow_error = {'operation': 'genericError', 'customer-key': ''}

        if self.order_status == 'ERR':
            self.logger.error(self.order_json['data']['order']['orderMsgs'])
            nso_util.notify_nso(workflow_error)
            return 'FAILURE'

        delete_vnf = get_order_items('deleteVapp', self.order_json, 1)

        vnf_id = delete_vnf['id']

        self.dbman.query('SELECT ns.ntw_policy,vnf.vnf_type, vnf.ntw_service_id '
                         'FROM network_service ns, vnf '
                         'WHERE vnf.vnf_id = ? '
                         'AND vnf.ntw_service_id = ns.ntw_service_id', (vnf_id,))

        res = self.dbman.fetchone()
        ntw_policy_list = res['ntw_policy'].split(',')
        vnf_type = res['vnf_type']
        service_id = res['ntw_service_id']

        # Not needed
        '''
        for ntw_policy in ntw_policy_list:
            if vnf_type in ntw_policy:
                ntw_policy_list.pop(ntw_policy)

        new_ntw_policy_list = ','.join(ntw_policy_list)
        
        self.logger.info('Updating NTW_POLICY column for Network Service %s. Data: %s ' % (service_id, new_ntw_policy_list))
        self.dbman.query('UPDATE network_service'
                         'SET ntw_policy = ?'
                         'WHERE ntw_service_id = ?', (new_ntw_policy_list, service_id))
        '''

        self.logger.info('Deleting VNF %s from database.' % vnf_id)
        self.dbman.delete_vnf(vnf_id)

        self.dbman.commit()

        # TODO notify NSO ERROR, VNFs creation failed

