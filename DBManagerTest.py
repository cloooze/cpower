#!/usr/bin/env python 

import unittest
from DBManager import DBManager

class DBManagerTest(unittest.TestCase):

	def setUp(self):
		self.dbman = DBManager()
	
	def tearDown(self):
		'''self.dbman.drop_table('cpower')'''
		
	def test_init(self):
		assert self.dbman is not None
		assert self.dbman.conn is not None
		assert self.dbman.cur is not None
		
	def test_init_default_table_creation(self):
		assert self.dbman.query('''SELECT * FROM customer''') is not None
		assert self.dbman.query('''SELECT * FROM network_service''') is not None
		assert self.dbman.query('''SELECT * FROM vnf''') is not None
		assert self.dbman.query('''SELECT * FROM vn_group''') is not None
		'''todo other tables'''
		
	def test_query_1(self):
		assert self.dbman.query('''INSERT INTO customer VALUES('test1', 'test1')''') is not None
		
		self.dbman.query('''SELECT * FROM customer WHERE customer_id="test1"''')
		
		self.assertEqual(self.dbman.fetchone(), ('test1', 'test1'))
		
	def test_query_2(self):
		tuple = ('test2', 'test2')
		assert self.dbman.query('''INSERT INTO customer VALUES(?, ?)''', tuple) is not None
		
		c_id = ('test2', )
		self.dbman.query('''SELECT * FROM customer WHERE customer_id=?''', c_id)
		
		self.assertEqual(self.dbman.fetchone(), tuple)
	
	def test_rollback(self):
		tuple = ('test2', 'test2')
		self.dbman.query('''INSERT INTO customer VALUES(?, ?)''', tuple)
		
		c_id = ('test2', )
		self.dbman.query('''SELECT * FROM customer WHERE customer_id=?''', c_id)
		
		self.assertEqual(self.dbman.fetchone(), tuple)
		
		self.dbman.rollback()
		
		assert self.dbman.fetchone() is None
	
	def test_save_customer(self):
		tuple = ('customer_001', 'customer_001_name')
		self.dbman.save_customer(tuple)
		c_id = ('customer_001', )
		self.dbman.query('''SELECT * FROM customer WHERE customer_id=?''', c_id)
		self.assertEqual(self.dbman.fetchone(), tuple)

		tuple = ('customer_002', None)
		self.dbman.save_customer(tuple)
		c_id = ('customer_002', )
		self.dbman.query('''SELECT * FROM customer WHERE customer_id=?''', c_id)
		self.assertEqual(self.dbman.fetchone(), tuple)

		
		
		
if __name__ == '__main__':
    unittest.main()
	