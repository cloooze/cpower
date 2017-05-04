#!/usr/bin/env python

import sqlite3

class DBManager(object):
	def __init__(self, db_name):
		self.conn = sqlite3.connect(db_name)
		self.cur = self.conn.cursor()
		
		self.cur.execute('''CREATE TABLE IF NOT EXISTS cpower (customer_id TEXT, route_target_left TEXT, vnf_type TEXT, PRIMARY KEY (customer_id)) ''')
		'''TODO add all table create statements'''
	
	def query(self, query, args=None, commit=True):
		if args == None:
			self.cur.execute(query,)
		else:
			self.cur.execute(query, args)
		if commit:
			self.conn.commit()
		return self.cur
		
	def fetchone(self):
		return self.curr.fetchone()
		
	def fetchall(self):
		return self.cur.fetchall()
	
	def __del__(self):
		self.conn.close()
		
	def save(self, args):
		self.cur.execute('''INSERT INTO cpower VALUES (?, ?, ?)''', args)
		self.conn.commit()
	
	def commit(self):
		self.conn.commit()
	
	def rollback(self):
		self.conn.rollback()
		
	'''Table specific save functions'''
	def save_customer(self, row):
		self.cur.execute('''INSERT INTO customer VALUES (?, ?)''', row)
	
	def save_network_service(self, row):
		'''TODO'''
	
	def save_vnf(self, row):
		'''TODO'''
		
	def save_vn_group(self, row):
		'''TODO'''
		
		
dbman = DatabaseManager("prova.db")

cpower = ('cust_1234', '123.123.123', 'vnf_type_0')
dbman.query('''INSERT INTO cpower VALUES (?, ?, ?)''', cpower)
cur = dbman.query('''SELECT * FROM cpower''')
for c in cur.fetchall():
	print c

