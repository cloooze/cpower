#!/usr/bin/env python 

import requests
import base64
import os
import sys
import json
import logging
import config as c
from nso_exception import NSOConnectionError

logger = logging.getLogger("cpower")

CREATE_SERVICE = {
    "cpwr:servicecreate": {
        "customer-key": "",
        "result": ""
    }
}

DELETE_SERVICE = {
    "cpwr:servicedelete": {
        "customer-key": "",
        "service-id": "",
        "result": ""
    }
}

CREATE_VNF = {
    "cpwr:vnfcreate": {
        "customer-key": "",
        "vnf-id": "",
        "result": "",
        "vnf-info": {
            "mgmt-ip": "",
            "left-ip": "",
            "right-ip": ""
        }
    }
}

DELETE_VNF = {
    "cpwr:vnfdelete": {
        "customer-key": "",
        "vnf-id": "",
        "result": ""
    }
}

WF_ERROR = {
    "cpwr:error": {
        "customer-key": "",
        "error-code": "",
        "error-message": ""
    }
}


def get_nso_json_data(params):
    if params['operation'] == 'createService':
        CREATE_SERVICE['cpwr:servicecreate']['customer-key'] = params['customer-key']
        CREATE_SERVICE['cpwr:servicecreate']['result'] = params['result']
        return CREATE_SERVICE
    if params['operation'] == 'deleteService':
        DELETE_SERVICE['cpwr:servicedelete']['customer-key'] = params['customer-key']
        DELETE_SERVICE['cpwr:servicedelete']['result'] = params['result']
        if params['result'] == 'success':
            DELETE_SERVICE['cpwr:servicedelete']['service-id'] = params['service-id']
        return DELETE_SERVICE
    if params['operation'] == 'createVnf':
        CREATE_VNF['cpwr:vnfcreate']['customer-key'] = params['customer-key']
        CREATE_VNF['cpwr:vnfcreate']['result'] = params['result']
        if params['result'] == 'success':
            CREATE_VNF['cpwr:vnfcreate']['vnf-id'] = params['vnf-id']
            CREATE_VNF['cpwr:vnfcreate']['vnf-info']['mgmt-ip'] = params['mgmt-ip']
            CREATE_VNF['cpwr:vnfcreate']['vnf-info']['left-ip'] = params['left-ip']
            CREATE_VNF['cpwr:vnfcreate']['vnf-info']['right-ip'] = params['right-ip']
        return CREATE_VNF
    if params['operation'] == 'deleteVnf':
        DELETE_VNF['cpwr:vnfdelete']['customer-key'] = params['customer-key']
        DELETE_VNF['cpwr:vnfdelete']['vnf-id'] = params['vnf-id']
        DELETE_VNF['cpwr:vnfdelete']['result'] = params['result']
        return DELETE_SERVICE
    if params['operation'] == 'genericError':
        WF_ERROR['cpwr:error']['customer-key'] = params['customer-key']
        WF_ERROR['cpwr:error']['error-code'] = params['error-code']
        WF_ERROR['cpwr:error']['error-message'] = params['error-message']
        return WF_ERROR
    return None


def notify_nso(params):
    count = 0
    while count < c.retry_n:
        json_data = get_nso_json_data(params)

        logger.info("Calling NSO API - PATCH /cpower/vnfconfig")
        logger.debug("Sending data: %s" % json_data)
        nso_endpoint = '%s%s' % (c.nso_server_address, c.nso_service_uri)
        h = {'Content-Type': 'application/vnd.yang.data+json'}
        try:
            resp = requests.patch(nso_endpoint, timeout=c.nso_service_timeout,
                                  auth=(c.nso_auth_username, c.nso_auth_password),
                                  headers=h, data=json.dumps(json_data, sort_keys=True))
            resp.raise_for_status()
        except requests.exceptions.HTTPError as r:
            logger.error(r)
            raise NSOConnectionError
        except requests.exceptions.Timeout:
            logger.warning("NSO connection timeout, trying again...")
            count += 1
        except requests.exceptions.RequestException as r:
            # logger.error("Something went very wrong during NSO API invocation...")
            logger.error(r)
            raise NSOConnectionError
        else:
            return resp
    logger.error("Could not get a response from NSO. Connection Timeout.")
    raise NSOConnectionError

