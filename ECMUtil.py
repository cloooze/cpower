#!/usr/bin/env python 

import requests
import base64
import json
import logging
import config as c
from ECMException import *


def get_ecm_api_auth():
    usr_pass = '%s:%s' % (c.ecm_service_api_header_auth_key, c.ecm_service_api_header_auth_value)
    b64_val = base64.b64encode(usr_pass)
    h = {
        'Authorization': 'Basic %s' % b64_val,
        'Content-Type': 'application/json',
        c.ecm_service_api_header_tenantId_key: c.ecm_service_api_header_tenantId_value
    }
    return h


def create_order(json_data=None, s=''):
    count = 0
    while count < c.retry_n:
        logging.info("Calling ECM API - POST /ecm_service/orders - Type %s" % s)
        logging.debug("Sending data: %s" % json_data)
        try:
            resp = requests.post('%s%s' % (c.ecm_server_address, c.ecm_service_api_orders),
                                 data=json.dumps(json_data),
                                 timeout=c.ecm_service_timeout,
                                 headers=get_ecm_api_auth(),
                                 verify=False)
            resp.raise_for_status()
        except requests.exceptions.HTTPError:
            raise ECMOrderResponseError
        except requests.exceptions.Timeout:
            logging.warning("ECM connection timeout, trying again...")
            count += 1
        except requests.exceptions.RequestException:
            raise ECMConnectionError
        else:
            logging.info("Response received: %s" % resp.status_code)
            logging.debug(resp.text)
            return resp
    logging.error("Could not get a response from ECM. Connection Timeout.")
    raise ECMConnectionError


def get_order(order_id=None):
    count = 0
    while count < c.retry_n:
        logging.info("Calling ECM API - GET /ecm_service/orders/%s" % order_id)
        try:
            resp = requests.get('%s%s%s' % (c.ecm_server_address, c.ecm_service_api_orders, order_id),
                                timeout=c.ecm_service_timeout,
                                headers=get_ecm_api_auth(),
                                verify=False)
            resp.raise_for_status()
        except requests.exceptions.HTTPError:
            raise ECMOrderResponseError
        except requests.exceptions.Timeout:
            logging.warning("ECM connection timeout, trying again...")
            count += 1
        except requests.exceptions.RequestException:
            logging.error("Something went very wrong during ECM API invocation...")
            raise ECMConnectionError
        else:
            return resp
    logging.error("Could not get a response from ECM. Connection Timeout.")
    raise ECMConnectionError


# Deprecated
def check_ecm_resp(resp):
    json_resp = json.loads(resp.text)
    try:
        order_req_status = json_resp['data']['order']['orderReqStatus']
    except KeyError:
        raise KeyError('Could not get data from JSON: [\'data\'][\'order\'][\'orderReqStatus\']')


# Use order_status got from env var instead of this function
def check_ecm_order_status(resp):
    json_resp = json.loads(resp.text)
    order_req_status = json_resp['data']['order']['orderReqStatus']
    if order_req_status == 'COM':
        return
    else:
        raise ECMOrderStatusError('ECM order status not COMPLETE.')
