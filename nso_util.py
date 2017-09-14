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

CREATE_DELETE_VNF_OK = {
    "customer": [
        {
            "customer-key": "",
            "result": "success",
            "service-id": "",
            "operation": "create",
            "vnf": [
                {
                    "operation": "",
                    "vnf-id": "",
                    "vnf-name": "",
                    "mgmt-ip": "",
                    "left-ip": "",
                    "right-ip": "",
                }
            ]
        }
    ]
}

CREATE_DELETE_VNF_NOK = {
    "customer": [
        {
            "customer-key": "",
            "result": "failed",
            "vnf": [
                {

                }
            ]
        }
    ]
}


DELETE_VNF_OK = {
    "customer": [
        {
            "customer-key": "",
            "operation": "remove",
            "result": "success",
            "service-id": "",
            "vnf-id": "",
            "vnf-name": "",
        }
    ]
}

DELETE_VNF_NOK = {
    "customer": [
        {
            "customer-key": "",
            "operation": "remove",
            "result": "failed",
            "service-id": "",
            "vnf-id": "",
            "vnf-name": "",
            "error-code": "2"
        }
    ]
}

DELETE_SERVICE_OK = {
    "customer": [
        {
            "customer-key": "",
            "operation": "remove",
            "result": "success",
            "service-id": ""
        }
    ]
}

DELETE_SERVICE_NOK = {
    "customer": [
        {
            "customer-key": "",
            "operation": "remove",
            "result": "failed",
            "service-id": "",
            "error-code": "2"
        }
    ]
}


def get_create_vnf_data_response(result, customer_id, service_id=None, vnf_list=None):
    if result == 'success':
        CREATE_DELETE_VNF_OK['customer'][0]['customer-key'] = customer_id
        CREATE_DELETE_VNF_OK['customer'][0]['service-id'] = service_id
        CREATE_DELETE_VNF_OK['customer'][0]['vnf'] = vnf_list
        return CREATE_DELETE_VNF_OK
    else:
        CREATE_DELETE_VNF_NOK['customer'][0]['customer-key'] = customer_id
        CREATE_DELETE_VNF_NOK['customer'][0]['vnf'] = vnf_list
        return CREATE_DELETE_VNF_NOK


def get_delete_vnf_data_response(result, customer_id, service_id, vnf_list):
    if result == 'success':
        CREATE_DELETE_VNF_OK['customer'][0]['customer-key'] = customer_id
        CREATE_DELETE_VNF_OK['customer'][0].pop('operation')
        CREATE_DELETE_VNF_OK['customer'][0].pop('service-id')
        CREATE_DELETE_VNF_OK['customer'][0]['vnf'] = vnf_list
        return CREATE_DELETE_VNF_OK
    else:
        CREATE_DELETE_VNF_NOK['customer'][0]['customer-key'] = customer_id
        CREATE_DELETE_VNF_NOK['customer'][0]['vnf'] = vnf_list
        return CREATE_DELETE_VNF_NOK


def get_delete_service_data_response(result, customer_id, service_id):
    if result == 'success':
        DELETE_SERVICE_OK['customer'][0]['customer-key'] = customer_id
        DELETE_SERVICE_OK['customer'][0]['service-id'] = service_id
        return DELETE_SERVICE_OK
    else:
        DELETE_SERVICE_NOK['customer'][0]['customer-key'] = customer_id
        DELETE_SERVICE_NOK['customer'][0]['service-id'] = service_id
        return DELETE_SERVICE_NOK


def notify_nso(operation, data):
    count = 0
    while count < c.retry_n:

        if operation == 'createService':
            nso_endpoint = c.nso_server_address + c.nso_service_uri_create_service
        elif operation == 'deleteService':
            nso_endpoint = c.nso_server_address + c.nso_service_uri_delete_service
        elif operation == 'deleteVnf':
            nso_endpoint = c.nso_server_address + c.nso_service_uri_modify_service
        elif operation == 'modifyService':
            nso_endpoint = c.nso_server_address + c.nso_service_uri_modify_service

        logger.info("Invoking NSO API %s - POST" % nso_endpoint)
        logger.debug("Sending data: %s" % json.dumps(data))

        h = {'Content-Type': 'application/vnd.yang.data+json'}
        try:
            logger.info("--- MOCK NSO NOTIFICATION ---")
            resp = None
            # Commented for TESTING PURPOSE
            #resp = requests.post(nso_endpoint, timeout=c.nso_service_timeout, auth=(c.nso_auth_username, c.nso_auth_password), headers=h, data=json.dumps(data, sort_keys=True))
            #resp.raise_for_status()
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
