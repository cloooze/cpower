#!/usr/bin/env python


import logging.config
from db_manager import DBManager
from event_manager import OrderManager


INTERNAL_ERROR = '100'
REQUEST_ERROR = '200'
NETWORK_ERROR = '300'


class DeleteVn(OrderManager):

    def __init__(self, order_status, order_id, source_api, order_json):
        self.order_json = order_json
        self.order_status = order_status
        self.order_id = order_id
        self.source_api = source_api

        self.dbman = DBManager()
        self.logger = logging.getLogger('cpower')

    def execute(self):
        # TODO check if the order is COM
        # remember that the flow will end up here twice as the deleteVn are two
        vn_id = self.get_order_items('deleteVn', self.order_json)[0]['id']
        self.dbman.query('SELECT vn_group_id FROM vn_group vn WHERE vn.vn_left_id=? OR vn.vn_right_id=?', (vn_id,))
        row = self.dbman.fetchone()

        if row is None:
            self.logger.info('Vn group associated to VNs %s already deleted.' % (vn_id))
        else:
            vn_group_id = row['vn_group_id']
            self.dbman.delete_vn_group(vn_group_id)

            # TODO notify NSO success with operation DELETE_SERVICE