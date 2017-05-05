#!/usr/bin/env python

import sqlite3

class DBManager(object):
	def __init__(self, db_name=None):
		if db_name == None:
			self.conn = sqlite3.connect(':memory:')
		else:
			self.conn = sqlite3.connect(db_name)
		self.cur = self.conn.cursor()
		
		with open('db_creation.sql') as db_creation:
			self.cur.executescript(db_creation.read())
		
	def __del__(self):
		self.conn.close()
		
	def query(self, query, args=None, commit=True):
		if args == None:
			self.cur.execute(query,)
		else:
			self.cur.execute(query, args)
		if commit == True:
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
		
	'''Table specific save functions'''
	def save_customer(self, row, commit=True):
		q = 'INSERT INTO customer VALUES (?, ?)'
		self.query(q, row, commit)
	
	def save_network_service(self, row, commit=True):
		q = 'INSERT INTO network_service VALUES (?, ?, ?, ?, ?, ?)'
		self.query(q, row, commit)
	
	def save_vnf(self, rowcommit=True):
		q = 'INSERT INTO vnf VALUES (?, ?, ?, ?, ?)'
		self.query(q, row, commit)
		
	def save_vn_group(self, rowcommit=True):
		q = 'INSERT INTO vn_group VALUES (?, ?, ?, ?, ?, ?)'
		self.query(q, row, commit)
	
	def drop_table(self, table_name):
		t = (table_name, )
		self.cur.execute('''DROP TABLE IF EXIST %s''' % table_name)
	