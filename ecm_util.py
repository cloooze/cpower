#!/usr/bin/env python 

import requests
import base64
import json
import logging
import config as c
from ecm_exception import *


def get_ecm_api_auth():
    usr_pass = '%s:%s' % (c.ecm_service_api_header_auth_key, c.ecm_service_api_header_auth_value)
    b64_val = base64.b64encode(usr_pass)
    h = {
        'Authorization': 'Basic %s' % b64_val,
        'Content-Type': 'application/json',
        c.ecm_service_api_header_tenantId_key: c.ecm_service_api_header_tenantId_value
    }
    return h


def invoke_ecm_api(param, api, http_verb, json_data=''):
    count = 0
    while count < c.retry_n:
        logging.debug("Sending data: %s" % json_data)
        try:
            if http_verb == 'GET':
                resp = requests.get('%s%s%s' % (c.ecm_server_address, api, param),
                                 timeout=c.ecm_service_timeout,
                                 headers=get_ecm_api_auth(),
                                 verify=False)
            elif http_verb == 'POST':
                resp = requests.post('%s%s' % (c.ecm_server_address, api),
                                     data=json.dumps(json_data),
                                    timeout=c.ecm_service_timeout,
                                    headers=get_ecm_api_auth(),
                                    verify=False)
            elif http_verb == 'PUT':
                resp = requests.put('%s%s%s' % (c.ecm_server_address, api, param),
                                     data=json.dumps(json_data),
                                     timeout=c.ecm_service_timeout,
                                     headers=get_ecm_api_auth(),
                                     verify=False)
            else:
                return None
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



def deploy_ovf_package(ovf_package_id, json_data):
    count = 0
    while count < c.retry_n:
        logging.info("Calling ECM API - POST /ovfpackages/%s/deploy" % ovf_package_id)
        logging.debug("Sending data: %s" % json_data)
        try:
            resp = requests.post('%s%s%s/deploy' % (c.ecm_server_address, c.ecm_service_api_ovfpackage, ovf_package_id),
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
