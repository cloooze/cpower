#!/usr/bin/env python

import sqlite3


class DBManager(object):
    def __init__(self, db_name=None):
        if db_name is None:
            self.conn = sqlite3.connect(':memory:')
        else:
            self.conn = sqlite3.connect(db_name)

        self.conn.row_factory = sqlite3.Row
        # self.conn.execute("PRAGMA foreign_keys = ON")

        self.cur = self.conn.cursor()

        with open('create_db.sql') as create_db:
            self.cur.executescript(create_db.read())

    def __del__(self):
        self.conn.close()

    def query(self, query, t=None, commit=True):
        if t is None:
            self.cur.execute(query, )
        else:
            self.cur.execute(query, t)
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
        q = 'INSERT INTO network_service VALUES (?, ?, ?, ?, ?, ?, ?, ?)'
        self.query(q, row, commit)

    def get_network_service(self, network_service_id):
        q = 'SELECT * FROM network_service WHERE ntw_service_id=?'
        self.query(q, (network_service_id, ))

    # VNF table

    def save_vnf(self, row, commit=True):
        q = 'INSERT INTO vnf VALUES (?, ?, ?, ?, ?)'
        self.query(q, row, commit)

    def get_vnf(self, vnf_id):
        q = 'SELECT * FROM vnf WHERE vnf_id=?'
        self.query(q, (vnf_id, ))

    # VN GROUP table

    def save_vn_group(self, row, commit=True):
        q = 'INSERT INTO vn_group("VNF_ID", "VN_LEFT_ID", "VN_LEFT_NAME", "VN_RIGHT_ID", "VN_RIGHT_NAME") VALUES (?, ' \
            '?, ?, ?, ?) '
        self.query(q, row, commit)

    def get_vnf(self, vnf_id):
        q = 'SELECT * FROM vnf WHERE vnf_id=?'
        self.query(q, (vnf_id, ))
