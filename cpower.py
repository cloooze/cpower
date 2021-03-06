#!/usr/bin/env python 

import sys
import logging.config
import ecm_util as ecm_util
import config as c
from logging.handlers import *
from ecm_exception import *
from event_create_order import CreateOrder
from event_create_order_vlink import CreateOrderVlink
from event_create_order_service import CreateOrderService
from event_create_order_vn import CreateOrderVn
from event_deploy_hot_package import DeployHotPackage
from event_delete_vn import DeleteVn
from event_modify_service import ModifyService
from event_modify_vlink import ModifyVlink
from event_delete_service import DeleteService
from event_delete_vnf import DeleteVnf
from utils import *

logger = logging.getLogger('cpower')


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
    logger.info('Starting script execution....')

    order_id = get_env_var('ECM_PARAMETER_ORDERID')
    source_api = get_env_var('ECM_PARAMETER_SOURCEAPI')
    order_status = get_env_var('ECM_PARAMETER_ORDERSTATUS')

    empty_env_var = get_empty_param(order_id=order_id, source_api=source_api, order_status=order_status)
    if empty_env_var is not None:
        logger.error("Environment variable [%s] not found or empty." % empty_env_var)
        sys.exit(1)

    logger.info("Environments variables found: ORDER_ID='%s' SOURCE_API='%s' ORDER_STATUS='%s'" % (
        order_id, source_api, order_status))

    try:
        order_resp = ecm_util.invoke_ecm_api(order_id, c.ecm_service_api_orders, 'GET')
    except ECMConnectionError as e:
        logger.exception(e)
        # TODO notify NSO
        sys.exit(1)

    order_json = json.loads(order_resp.text)

    events = {
        'createOrder': [
            CreateOrder(order_status, order_id, source_api, order_json),
            CreateOrderService(order_status, order_id, source_api, order_json),
            CreateOrderVlink(order_status, order_id, source_api, order_json),
            CreateOrderVn(order_status, order_id, source_api, order_json)
        ],
        'modifyService': ModifyService(order_status, order_id, source_api, order_json),
        'modifyVLink': ModifyVlink(order_status, order_id, source_api, order_json),
        'deleteService': DeleteService(order_status, order_id, source_api, order_json),
        'deleteVn': DeleteVn(order_status, order_id, source_api, order_json),
        'deleteVapp': DeleteVnf(order_status, order_id, source_api, order_json),
        'deployHotPackage' : DeployHotPackage(order_status, order_id, source_api, order_json)
    }

    try:
        try:
            event = events[source_api]
        except KeyError:
            logger.error('Operation [%s] not handled by workflow.' % source_api)
            sys.exit(1)

        if source_api == 'createOrder':
            if get_order_items('createVLink', order_json, 1) is not None:
                event = events['createOrder'][2]
            elif get_order_items('createService', order_json, 1) is not None:
                event = events['createOrder'][1]
            elif get_order_items('createVn', order_json, 1) is not None:
                event = events['createOrder'][3]
            else:
                event = events['createOrder'][0]

        result = event.execute()

        event.notify()

        event.rollback()

        logger.info('End of script execution: [%s]' % ('SUCCESS' if not result else 'FAILURE'))
        sys.exit(0 if not result else 1)
    except Exception:  # fix this
        logger.exception('Something went wrong during script execution.')
        sys.exit(1)


if __name__ == '__main__':
    main()
else:
    print 'sorry :('

