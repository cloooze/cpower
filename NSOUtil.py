#!/usr/bin/env python 

import requests
import base64
import os
import sys
import json
import logging
import config as c
from NSOException import NSOConnectionError

CISCO_NSO_JSON = {
            "cpwr:vnfconfig" : {
                "customer-key" : "",
                "vnf-id" : "",
                "vnf-info" : {
                    "mgmt-ip" : "",
                    "cust-ip" : "",
                    "ntw-ip" : ""
                }
            }
        }


def get_nso_json_data(params):
    CISCO_NSO_JSON['cpwr:vnfconfig']['customer-key'] = params['customer-key']
    CISCO_NSO_JSON['cpwr:vnfconfig']['vnf-id'] = params['vnf-id']
    CISCO_NSO_JSON['cpwr:vnfconfig']['vnf-info']['mgmt-ip'] = params['mgmt-ip']
    CISCO_NSO_JSON['cpwr:vnfconfig']['vnf-info']['cust-ip'] = params['cust-ip']
    CISCO_NSO_JSON['cpwr:vnfconfig']['vnf-info']['ntw-ip'] = params['ntw-ip']
    return CISCO_NSO_JSON


def notify_nso(params):
    count = 0
    while count < c.retry_n:
        vnfconfig_json_data = get_nso_json_data(params)
        logging.info("Calling NSO API - PATCH /cpower/vnfconfig")
        logging.debug("Sending data: %s" % vnfconfig_json_data)
        nso_endpoint = '%s%s' % (c.nso_server_address, c.nso_service_uri)
        h = {'Content-Type': 'application/vnd.yang.data+json'}
        try:
            resp = requests.patch(nso_endpoint, timeout=c.nso_service_timeout,
                                  auth=(c.nso_auth_username, c.nso_auth_password),
                                  headers=h, data=json.dumps(vnfconfig_json_data, sort_keys=True))
            resp.raise_for_status()
        except requests.exceptions.HTTPError:
            raise NSOConnectionError
        except requests.exceptions.Timeout:
            logging.warning("NSO connection timeout, trying again...")
            count += 1
        except requests.exceptions.RequestException:
            logging.error("Something went very wrong during NSO API invocation...")
            raise NSOConnectionError
        else:
            return resp
    logging.error("Could not get a response from NSO. Connection Timeout.")
    raise NSOConnectionError
