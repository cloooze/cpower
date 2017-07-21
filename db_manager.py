#!/usr/bin/env python

import sqlite3
from logging.handlers import *


class DBManager(object):
    
    logger = logging.getLogger('cpowersql')
    
    def __init__(self, db_name=None):
        if db_name is None:
            self.conn = sqlite3.connect(':memory:')
        else:
            self.conn = sqlite3.connect(db_name)

        self.conn.row_factory = sqlite3.Row

        # Disabled ONLY for testing purposes
        self.conn.execute("PRAGMA foreign_keys = ON")

        self.cur = self.conn.cursor()

        with open('create_db.sql') as create_db:
            self.cur.executescript(create_db.read())

        DBManager.setup_logging()

    def __del__(self):
        self.conn.close()

    @staticmethod
    def setup_logging():
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
        DBManager.logger.setLevel(logging.DEBUG)
        handler = RotatingFileHandler('log/db_trace.log', maxBytes=10485760, backupCount=10)
        handler.setFormatter(formatter)
        DBManager.logger.addHandler(handler)

    def query(self, query, t=None, commit=True):
        if t is None:
            self.cur.execute(query, )
            self.logger.info(query)
        else:
            self.cur.execute(query, t)
            self.logger.info(query.replace('?', '%s') % t)

        if commit is True:
            self.conn.commit()
        return self.cur

    def fetchone(self):
        return self.cur.fetchone()

    def fetchall(self):
        return self.cur.fetchall()

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    # Table specific save and get functions

    # Customer table
    def save_customer(self, row, commit=True):
        q = 'INSERT INTO customer VALUES (?, ?)'
        self.query(q, row, commit)

    def get_customer(self, customer_id):
        q = 'SELECT * FROM customer WHERE customer_id=?'
        self.query(q, (customer_id, ))

    def delete_customer(self, condition, commit=True):
        q = 'DELETE FROM customer WHERE customer_id=?'
        self.query(q, condition, commit)

    # Network Service table

    def save_network_service(self, row, commit=True):
        q = 'INSERT INTO network_service VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)'
        self.query(q, row, commit)

    def get_network_service(self, network_service_id):
        q = 'SELECT * FROM network_service WHERE ntw_service_id=?'
        self.query(q, (network_service_id, ))

    # VNF table

    def save_vnf(self, row, commit=True):
        q = 'INSERT INTO vnf VALUES (?, ?, ?, ?, ?, ?, ?, ?)'
        self.query(q, row, commit)

    def get_vnf(self, vnf_id):
        q = 'SELECT * FROM vnf WHERE vnf_id=?'
        self.query(q, (vnf_id, ))

    def delete_vnf(self, condition, commit=True):
        q = 'DELETE FROM vnf WHERE vnf_id=?'
        self.query(q, (condition, ), commit)

    # VN GROUP table

    def save_vn_group(self, row, commit=True):
        q = 'INSERT INTO vn_group("VN_LEFT_ID", "VN_LEFT_NAME", "VN_LEFT_VIMOBJECT_ID", "VN_RIGHT_ID",' \
            ' "VN_RIGHT_NAME", "VN_RIGHT_VIMOBJECT_ID") VALUES (?, ?, ?, ?, ?, ?)'
        return self.query(q, row, commit).lastrowid

    def delete_vn_group(self, condition, commit=True):
        q = 'DELETE FROM vn_group WHERE vn_group_id=?'
        self.query(q, condition, commit)

    # VM table

    def save_vm(self, row, commit=True):
        q = 'INSERT INTO vm VALUES (?, ?, ?)'
        self.query(q, row, commit)

    def get_vm(self, vm_id):
        q = 'SELECT * FROM vm WHERE vm_id=?'
        self.query(q, (vm_id, ))

    def delete_vm(self, condition, commit=True):
        q = 'DELETE FROM vm WHERE vm_id=?'
        self.query(q, condition, commit)


    #VMVNIC table


    def save_vmvnic(self, row, commit=True):
        q = 'INSERT INTO vmvnic VALUES (?, ?, ?, ?, ?)'
        self.query(q, row, commit)

    def get_vmvnic(self, vm_id):
        q = 'SELECT * FROM vmvnic WHERE vmvnic_id=?'
        self.query(q, (vm_id, ))

    def delete_vmvnic(self, condition, commit=True):
        q = 'DELETE FROM vmvnic WHERE vmvnic_id=?'
        self.query(q, condition, commit)



    def save_order(self, row, commit=True):
        q = 'INSERT INTO orders VALUES (?, ?, ?)'
        self.query(q, row, commit)

    def get_order(self, order_id):
        q = 'SELECT * FROM orders WHERE order_id=?'
        self.query(q, (order_id, ))
