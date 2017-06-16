#!/usr/bin/env python 

import requests
import base64
import json
import logging
import config as c
from ecm_exception import *

logger = logging.getLogger("cpower")

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
        logger.info('Invoking ECM API %s%s - %s ' % (api, (param if param is not None else ''), http_verb))
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
                logger.debug("Sending data: %s" % json_data)
            elif http_verb == 'PUT':
                resp = requests.put('%s%s%s' % (c.ecm_server_address, api, param),
                                     data=json.dumps(json_data),
                                     timeout=c.ecm_service_timeout,
                                     headers=get_ecm_api_auth(),
                                     verify=False)
                logger.debug("Sending data: %s" % json_data)
            else:
                return None
            resp.raise_for_status()
            check_ecm_resp(resp)
        except requests.exceptions.HTTPError:
            raise ECMConnectionError('HTTP response code is not 200')
        except requests.exceptions.Timeout:
            logger.warning("ECM connection timeout, trying again...")
            count += 1
        except requests.exceptions.RequestException:
            raise ECMConnectionError('Could not get a response from ECM.')
        else:
            return resp
    raise ECMConnectionError('Could not get a response from ECM. Connection Timeout.')


def deploy_ovf_package(ovf_package_id, json_data):
    count = 0
    while count < c.retry_n:
        logger.info('Invoking ECM API /ecm_service/ovfpackages/%s/deploy - POST' % ovf_package_id)
        try:
            resp = requests.post('%s%s%s/deploy' % (c.ecm_server_address, c.ecm_service_api_ovfpackage, ovf_package_id),
                                 data=json.dumps(json_data),
                                 timeout=c.ecm_service_timeout,
                                 headers=get_ecm_api_auth(),
                                 verify=False)
            logger.debug("Sending data: %s" % json_data)
            resp.raise_for_status()
            check_ecm_resp(resp)
        except requests.exceptions.HTTPError:
            raise ECMConnectionError('HTTP response code is not 200')
        except requests.exceptions.Timeout:
            logger.warning("ECM connection timeout, trying again...")
            count += 1
        except requests.exceptions.RequestException:
            raise ECMConnectionError('Could not get a response from ECM.')
        else:
            return resp
    raise ECMConnectionError('Could not get a response from ECM. Connection Timeout.')


def check_ecm_resp(resp):
    resp_json = json.loads(resp.text)
    if resp_json['status']['reqStatus'] != 'SUCCESS':
        raise ECMReqStatusError(resp_json['status']['msgs'])

