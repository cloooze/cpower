#!/usr/bin/env python 

import sqlite
import requests
import base64
import os
import sys
import json
import logging
from time import sleep
import config as c
import ECMManager
import DBManager
import MyException

def get_customer_order_param(s, json_data):
	for custom_param in json_data:
		if s == custom_param['tag']:
			return custom_param['value']
	return None

def get_order_item(order_item_name, json_data):
	order_items = json_data['data']['order']['orderItems']
	for order_item in order_items:
		item_name = order_item.keys()[0]
		if item_name == order_item_name:
			return order_item[item_name]
	return None

def get_json_from_file(file_name):
    with open(file_name) as file:
        data = json.load(file)
    return data

def execute_step_1():
	logging.info('executing step1...')

def execute_step_2():
	logging.info('executing step2...')

def execute_step_3():
	logging.info('executing step3...')

def main():
	script_dir = os.path.dirname(os.path.realpath(__file__))
	logging.basicConfig(filename=os.path.join(os.sep, script_dir, 'cpower.log'), level=logging.DEBUG, format='%(asctime)s %(levelname)s %(message)s')

	#get environment variables set by ECMSID
	if ('ECM_PARAMETER_ORDERID' and 'ECM_PARAMETER_SOURCEAPI') in os.environ:
		order_id, source_api = os.environ['ECM_PARAMETER_ORDERID'], os.environ['ECM_PARAMETER_SOURCEAPI']
		logging.info('Env vars set by ECMSID %s %s', order_id, source_api)
	else:
		logging.error('Environment variables ECM_PARAMETER_ORDERID and/or ECM_PARAMETER_SOURCEAPI not found')
		sys.exit(1)

	dbman = DBManager('cpower.db')
	ecmman = ECMManager()
	
	try:
		'''Getting ECM order'''
		order_resp = ecmman.get_order(order_id)
		logging.info("Response received: %s" % order_resp.status_code)
		logging.debug(order_resp.text)
		order_json = json.loads(order_resp.text)
		
		'''Getting customer order params from ECM order'''
		customer_order_params = order_json['data']['order']['customOrderParams']
	except ECMOrderResponseError as oe:
		logging.error('ECM response status code not equal to 2**, stopping script execution.')
		sys.exit(1)
	except ECMConnectionError as ce:
		logging.error('Impossible to contact ECM, stopping script execution.')
		logging.exception(ce)
		logging.debug(ce) '''???'''
		sys.exit(1)

	try:
		if source_api == 'createOrder':
			opearation = get_customer_order_param('operation', customer_order_params)
			step = get_customer_order_param('step', customer_order_params)
			
			rt_left = get_customer_order_param('rt-left', customer_order_params)
			rt_right = get_customer_order_param('rt-right', customer_order_params)
			rt_mgmt = get_customer_order_param('rt-mgmt', customer_order_params)
			customer_id = get_customer_order_param('Cust_Key', customer_order_params)
			vnf_type = get_customer_order_param('vnf_type', customer_order_params)
			
			service_id = get_order_item('createService', order_json)['id']
			service_name = get_order_item('createService', order_json)['name']
			'''
			if flow_step is None or rt_left is None or rt_right is None or customer_id is None:
				logging.error('Could not get all the required customer order parameters, stopping script execution.')
				sys.exit(1)
			'''
			
			#do first step		
			if opearation == 'create':
				'''First step'''
				if step == None:
					try:
						'''checking order status'''
						ecmman.check_ecm_order_status(order_resp)
					except ECMOrderStatusError as se:
						'''no rollback required here as we're at the first step, notify nso immidiatly'''
						'''---TODO notify NSO---'''
						logging.exceptiom(se)
						sys.exit(1)
						
					cur = dbman.query('''SELECT * FROM cpower WHERE customer_key=123''')
					if cc.rowcount > 0:
						'''The request is to add a new VNF to an existing one, what to do?'''
					else:
						customer_row = (customer_id, )
						ntw_service_row = (customer_id, 
											vnf_type, 
											'ntw_service_id',
											'ntw_service_name',
											rt_left,
											rt_right,
											'rt-mgmt',
											NULL)
						try:
							dbman.save_customer(customer_row)
							dbman.query('''INSERT INTO cpower VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', entry, False)
							logging.info('Data succesfully added to cpower table: %s' % (entry,))
						except sqlite3.IntegrityError:
							logging.error('Could not insert the following data to cpower table %s' % (entry,))
							logging.error('Stopping script execution.')
							sys.exit(1)
						
					
					
					get_json_from_file('./filename.json')
					
					'''put step2 in customer order param (in operation tag) '''
					if vnf_type == 'csr1000':
						'''TODO substitute attributes in JSON file accordin to vnf_type'''
					elif vnf_type == 'fortinet':
						'''TODO substitute attributes in JSON file accordin to vnf_type'''
						
					try:
						ecmman.create_order(json_data)
					except ECMOrderResponseError as re:
						logging.error('ECM error response.')
					except ECMConnectionError as ce:
						logging.error('Impossible to contact ECM.')
					else:
						dbman.commit()
				elif step == '2':
					'''TODO step 2'''
				elif step == '3':
					'''TODO step 3'''
								
			elif operation == 'add':
				'''TODO add operation of a second VNF to the Network Service'''

			
			
			
					
				
			  
		elif source_api == 'deleteService':
			exit_code = _processTermination(order_id)
		else:
			logging.info('%s operation not handled' % source_api)
		
		sys.exit(0)
	except Exception as e:
		logging.exception('Exception encountered during stript execution.')
		sys.exit(1)

if __name__ == '__main__':
	main()
else:
	print 'sorry :(' 