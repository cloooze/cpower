#!/usr/bin/env python

from event import Event
import nso_util

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

        delete_vnf = self.get_order_items('deleteVnf', self.order_json)[0]

        vnf_id = delete_vnf['id']

        self.dbman.delete_vnf(vnf_id)

        # TODO modify VLINK???
        # TODO notify NSO success with operation DELETE_VNF