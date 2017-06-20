#!/usr/bin/env python 

import sqlite3
import os
import sys
import json
from logging.handlers import *
import logging
import logging.config
import ecm_util as ecm_util
import nso_util as nso_util
from db_manager import DBManager
from ecm_exception import *
from nso_exception import *
import config as c
from event_create_order import CreateOrder
from event_delete_service import DeleteService
from event_delete_vn import DeleteVn
from event_deploy_ovf_package import DeployOvfPackage
from event_modify_service import ModifyService
from utils import *


logger = logging.getLogger('cpower')
e = {'SUCCESS': 0, 'FAILURE': 1}


def _exit(exit_mess):
    e = {'SUCCESS': 0, 'FAILURE': 1}
    logger.info('End of script execution - %s' % exit_mess)
    try:
        sys.exit(e[exit_mess])
    except (NameError, KeyError):
        sys.exit(1)


def setup_logging():
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    logger.setLevel(logging.DEBUG)
    if not os.path.exists('log'):
        os.makedirs('log')
    handler = RotatingFileHandler('log/cpower.log', maxBytes=10485760, backupCount=10)
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def main():
    setup_logging()
    logger.info('Starting script execution...')

    # Getting env var set by ECMSID
    order_id = get_env_var('ECM_PARAMETER_ORDERID')
    source_api = get_env_var('ECM_PARAMETER_SOURCEAPI')
    order_status = get_env_var('ECM_PARAMETER_ORDERSTATUS')

    # Checking if some of the env var are empty
    empty_env_var = get_empty_param(order_id=order_id, source_api=source_api, order_status=order_status)
    if empty_env_var is not None:
        logger.error("Environment variable '%s' not found or empty." % empty_env_var)
        _exit('FAILURE')

    try:
        logger.info("Environments variables found: ORDER_ID='%s' SOURCE_API='%s' ORDER_STATUS='%s'"
                    % (order_id, source_api, order_status))
        # Getting ECM order using the ORDER_ID env var
        order_resp = ecm_util.invoke_ecm_api(order_id, c.ecm_service_api_orders, 'GET')
    except ECMConnectionError as e:
        logger.exception(e)
        # TODO notify NSO
        _exit('FAILURE')

    order_json = json.loads(order_resp.text)

    events = {'createOrder': CreateOrder(order_status, order_id, source_api, order_json),
                'deployOvfPackage': DeployOvfPackage(order_status, order_id, source_api, order_json),
                'modifyService': ModifyService(order_status, order_id, source_api, order_json),
                'deleteVn': DeleteVn(order_status, order_id, source_api, order_json)}

    try:
        event = events[source_api]
    except KeyError:
        logger.error('Operation %s not handled by workflow.' % source_api)
        _exit('FAILURE')

    try:
        result = event.execute()

        logger.info('End of script execution - %s' % result)
        sys.exit(e[result])
    except Exception: # fix this
        logger.exception('Something went wrong during script execution.')
        _exit('FAILURE')

if __name__ == '__main__':
    main()
else:
    print 'sorry :('
