#!/usr/bin/env python 

import unittest
from db_manager import DBManager


class DBManagerTest(unittest.TestCase):
    def setUp(self):
        self.dbman = DBManager()

    def tearDown(self):
        pass

    def test_init(self):
        self.assertIsNotNone(self.dbman)
        self.assertIsNotNone(self.dbman.conn)
        self.assertIsNotNone(self.dbman.cur)

    def test_init_default_table_creation(self):
        self.assertIsNotNone(self.dbman.query('''SELECT * FROM customer'''))
        self.assertIsNotNone(self.dbman.query('''SELECT * FROM network_service'''))
        self.assertIsNotNone(self.dbman.query('''SELECT * FROM vnf'''))
        self.assertIsNotNone(self.dbman.query('''SELECT * FROM vn_group'''))

    def test_query_customer_01(self):
        self.assertIsNotNone(self.dbman.query('''INSERT INTO customer VALUES('test1', 'test1')'''))
        self.dbman.query('''SELECT * FROM customer WHERE customer_id="test1"''')
        self.assertEqual('test1', self.dbman.fetchone()['customer_id'])

    def test_query_customer_02(self):
        t = ('test2', 'test2')
        self.assertIsNotNone(self.dbman.query('''INSERT INTO customer VALUES(?, ?)''', t))
        c_id = ('test2',)
        self.dbman.query('''SELECT * FROM customer WHERE customer_id=?''', c_id)
        self.assertEqual('test2', self.dbman.fetchone()['customer_id'])

    def test_query_network_service_01(self):
        t = ('test2', 'test2', 'test2', 'test2', 'test2', 'test2', 'test2', 'test2')
        self.assertIsNotNone(self.dbman.query('''INSERT INTO network_service VALUES(?, ?, ?, ?, ?, ?, ?, ?)''', t))
        c_id = ('test2',)
        self.dbman.query('''SELECT * FROM network_service WHERE ntw_service_id=?''', c_id)
        self.assertEqual('test2', self.dbman.fetchone()['ntw_service_id'])

    def test_query_vnf_01(self):
        t = ('test2', 'test2', 'test2', 'test2', 'test2')
        self.assertIsNotNone(self.dbman.query('''INSERT INTO vnf VALUES(?, ?, ?, ?, ?)''', t))
        c_id = ('test2',)
        self.dbman.query('''SELECT * FROM vnf WHERE vnf_id=?''', c_id)
        self.assertEqual('test2', self.dbman.fetchone()['vnf_id'])

    def test_query_vn_group_01(self):
        t = ('test2', 'test2', 'test2', 'test2', 'test2')
        self.assertIsNotNone(self.dbman.query(
            '''INSERT INTO vn_group("VNF_ID", "VN_LEFT_ID", "VN_LEFT_NAME", "VN_RIGHT_ID", "VN_RIGHT_NAME") VALUES(?, 
            ?, ?, ?, ?)''', t))
        self.dbman.query('''SELECT * FROM vn_group WHERE vn_group_id=1''')
        self.assertEqual(1, self.dbman.fetchone()['vn_group_id'])

    def test_rollback(self):
        t = ('test2', 'test2')
        self.dbman.query('''INSERT INTO customer VALUES(?, ?)''', t)
        c_id = ('test2',)
        self.dbman.query('''SELECT * FROM customer WHERE customer_id=?''', c_id)
        self.assertEqual('test2', self.dbman.fetchone()['customer_id'])
        self.dbman.rollback()
        self.assertIsNone(self.dbman.fetchone())

    def test_fetchone_01(self):
        t = ('customer_001', 'customer_001_name')
        self.dbman.save_customer(t)
        self.dbman.query('''SELECT * FROM customer WHERE customer_id="customer_001"''')
        self.assertEqual('customer_001', self.dbman.fetchone()['customer_id'])

    def test_fetchall_01(self):
        t_1 = ('customer_001', 'customer_001_name')
        t_2 = ('customer_002', 'customer_002_name')
        self.dbman.save_customer(t_1)
        self.dbman.save_customer(t_2)
        self.dbman.query('''SELECT * FROM customer''')
        res = self.dbman.fetchall()
        self.assertEqual(2, len(res))
        self.assertEqual('customer_001', res[0]['customer_id'])
        self.assertEqual('customer_002', res[1]['customer_id'])

    # Save table specific test cases

    def test_save_customer_01(self):
        t = ('customer_001', 'customer_001_name')
        self.dbman.save_customer(t)
        c_id = ('customer_001',)
        self.dbman.query('''SELECT * FROM customer WHERE customer_id=?''', c_id)
        self.assertEqual('customer_001', self.dbman.fetchone()['customer_id'])

    def test_save_customer_02(self):
        t = ('customer_002', None)
        self.dbman.save_customer(t)
        c_id = ('customer_002',)
        self.dbman.query('''SELECT * FROM customer WHERE customer_id=?''', c_id)
        self.assertEqual('customer_002', self.dbman.fetchone()['customer_id'])

    def test_save_network_service_01(self):
        t = ('ntw_002', 'ntw_002', 'ntw_002', 'ntw_002', 'ntw_002', 'ntw_002', 'ntw_002', 'ntw_002')
        self.dbman.save_network_service(t)
        c_id = ('ntw_002',)
        self.dbman.query('''SELECT * FROM network_service WHERE ntw_service_id=?''', c_id)
        self.assertEqual('ntw_002', self.dbman.fetchone()['ntw_service_id'])

    def test_save_vnf_01(self):
        t = ('vnf_002', 'vnf_002', 'vnf_002', 'vnf_002', 'vnf_002')
        self.dbman.save_vnf(t)
        c_id = ('vnf_002',)
        self.dbman.query('''SELECT * FROM vnf WHERE vnf_id=?''', c_id)
        self.assertEqual('vnf_002', self.dbman.fetchone()['vnf_id'])

    def test_save_vn_group_01(self):
        t = ('vn_001', 'vn_001', 'vn_001', 'vn_001', 'vn_001')
        self.dbman.save_vn_group(t)
        self.dbman.query('''SELECT * FROM vn_group WHERE vn_group_id=1''')
        self.assertEqual(1, self.dbman.fetchone()['vn_group_id'])

    # Get table specific test cases

    def test_get_customer_01(self):
        t = ('customer_001', 'customer_001_name')
        self.dbman.save_customer(t)
        self.dbman.get_customer('customer_001')
        self.assertEqual('customer_001', self.dbman.fetchone()['customer_id'])

    def test_get_customer_02(self):
        t = ('customer_001', 'customer_001_name')
        self.dbman.save_customer(t)
        self.dbman.get_customer('customer_001')
        r = self.dbman.fetchall()
        self.assertEqual(1, len(r))
        self.assertEqual('customer_001', r[0]['customer_id'])

    def test_get_network_service_01(self):
        t_1 = ('ntw_001', 'ntw_001', 'ntw_001', 'ntw_001', 'ntw_001', 'ntw_001', 'ntw_001', 'ntw_001')
        t_2 = ('ntw_002', 'ntw_002', 'ntw_002', 'ntw_002', 'ntw_002', 'ntw_002', 'ntw_001', 'ntw_001')
        self.dbman.save_network_service(t_1)
        self.dbman.save_network_service(t_2)
        self.dbman.get_network_service('ntw_001')
        self.assertEqual('ntw_001', self.dbman.fetchone()['ntw_service_id'])

    def test_get_network_service_02(self):
        t_1 = ('ntw_001', 'ntw_001', 'ntw_001', 'ntw_001', 'ntw_001', 'ntw_001', 'ntw_001', 'ntw_001')
        self.dbman.save_network_service(t_1)
        self.dbman.get_network_service('ntw_002')
        self.assertIsNone(self.dbman.fetchone())

if __name__ == '__main__':
    unittest.main()
