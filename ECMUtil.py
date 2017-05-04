#!/usr/bin/env python 

import requests
import base64
import os
import sys
import json
import logging
import config as c
import MyException

class ECMUtil(object):

  def get_ecm_api_auth():
    usrPass = '%s:%s' % (c.ecm_service_api_header_auth_key, c.ecm_service_api_header_auth_value)
    b64Val = base64.b64encode(usrPass)
    h = {
        'Authorization': 'Basic %s' % b64Val,
        'Content-Type': 'application/json',
        c.ecm_service_api_header_tenantId_key: c.ecm_service_api_header_tenantId_value
        }
    return h
	
  def create_order(json_data=None, s=''):
	c = 0
	while c < c.retry_n:
		logging.info("Calling ECM API - POST /ecm_service/orders - Type %s" % s)
		logging.debug("Sending data: %s" % json_data)
		try:
			resp = requests.post('%s%s' % (c.ecm_server_address, c.ecm_service_api_orders),
				data = json.dumps(json_data),
				timeout = c.ecm_service_timeout,
				headers = get_ecm_api_auth(),
				verify=False)
			resp.raise_for_status()
		except requests.exceptions.HTTPError as err:
			raise ECMOrderResponseError
		except requests.exceptions.Timeout:
			if c == c.retry_n:
				logging.error("ECM connection timed out. I wont try again.")
				raise ECMConnectionError
			else:
				logging.warning("ECM connection Timeout, trying again...")
				c += 1
		except requests.exceptions.RequestException as e
			raise ECMConnectionError
		else:
			logging.info("Response received: %s" % resp.status_code)
			logging.debug(resp.text)
			return resp
	
  def get_order(order_id=None):
	c = 0
	while c < c.retry_n:
		logging.info("Calling ECM API - GET /ecm_service/orders/%s" % order_id)
		try:
			resp = requests.get('%s%s%s'  % (c.ecm_server_address, c.ecm_service_api_orders, order_id),
				timeout=c.ecm_service_timeout,
				headers=get_ecm_api_auth(),
				verify=False)
			resp.raise_for_status()
		except requests.exceptions.HTTPError as err:
			raise ECMOrderResponseError
		except requests.exceptions.Timeout:
			if c == c.retry_n:
				logging.error("ECM connection timed out. I wont try again.")
				raise ECMConnectionError
			else:
				logging.warning("ECM connection Timeout, trying again...")
				c += 1
		except requests.exceptions.RequestException as e
			raise ECMConnectionError
		else:
			return resp
	
	'''deprecated'''
	def check_ecm_resp(resp):    
		json_resp = json.loads(resp.text)
		try:
			order_req_status = json_resp['data']['order']['orderReqStatus']
		except KeyError:
			raise KeyError('Could not get data from JSON: [\'data\'][\'order\'][\'orderReqStatus\']')
		
	
	def check_ecm_order_status(resp):
		json_resp = json.loads(resp.text)
		order_req_status = json_resp['data']['order']['orderReqStatus']
		if order_req_status == 'COM':
			return
		else:
			raise ECMOrderStatusError('ECM order status not COMPLETE.')
	
		

