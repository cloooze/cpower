#!/usr/bin/env python

from event import Event
import nso_util

INTERNAL_ERROR = '100'
REQUEST_ERROR = '200'
NETWORK_ERROR = '300'


class DeleteVn(Event):

    def __init__(self, order_status, order_id, source_api, order_json):
        super(DeleteVn, self).__init__()

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

        delete_vn = self.get_order_items('deleteVn', self.order_json)[0]

        vn_id = delete_vn['id']

        self.dbman.query('SELECT vn_group_id FROM vn_group vn WHERE vn.vn_left_id=? OR vn.vn_right_id=?', (vn_id,))
        row = self.dbman.fetchone()

        if row is None:
            self.logger.info('Vn group associated to VN [%s] already deleted.' % (vn_id))
        else:
            vn_group_id = row['vn_group_id']
            self.dbman.delete_vn_group(vn_group_id)

        # TODO notify NSO success with operation DELETE_SERVICE

    def rollback(self):
        pass