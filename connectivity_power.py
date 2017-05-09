#!/usr/bin/env python 

import sqlite3
import requests
import base64
import os
import sys
import json
import logging
from time import sleep
import config as c
import ECMUtil
import DBManager
from MyException import *


def check_custom_parmas(*args):
    for param in args:
        if param is None:
            return 'param_name'

def get_env_var(var_name):
    if var_name in os.environ:
        return os.environ[var_name]
    return None


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


def _exit(exit_mess):
    e = {'SUCCESS': 0, 'FAILURE': 1}
    logging.info('End of script execution - %s' % exit_mess)
    try:
        sys.exit(e[exit_mess])
    except (NameError, KeyError):
        sys.exit(1)

def main():
    script_dir = os.path.dirname(os.path.realpath(__file__))
    logging.basicConfig(filename=os.path.join(os.sep, script_dir, 'cpower.log'), level=logging.DEBUG,
                        format='%(asctime)s %(levelname)s %(message)s')

    logging.info('Starting script execution...')

    order_id = get_env_var('ECM_PARAMETER_ORDERID')
    source_api = get_env_var('ECM_PARAMETER_SOURCEAPI')
    order_status = get_env_var('ECM_PARAMETER_ORDERSTATUS')

    if (order_id or source_api or order_status) is None:
        logging.error('ORDERID, SOURCEAPI or ORDERSTATUS not found in environment variables.')
        _exit('FAILURE')

    dbman = DBManager('cpower.db')
    ecmutil = ECMUtil()

    try:
        # Getting ECM order
        logging.info('Environments variables found: '
                     'ORDER_ID=\'%s\' SOURCE_API=\'%s\' ORDERSTATUS=\'%s\'' % (order_id, source_api, order_status))
        order_resp = ecmutil.get_order(order_id)
        logging.info("Response received: %s" % order_resp.status_code)
        logging.debug(order_resp.text)
    except ECMOrderResponseError as oe:
        logging.error('ECM response status code not equal to 2**.')
        _exit('FAILURE')
    except ECMConnectionError as ce:
        logging.exception('Impossible to contact ECM.')
        _exit('FAILURE')

    order_json = json.loads(order_resp.text)
    # Getting customer order params from response
    customer_order_params = order_json['data']['order']['customOrderParams']

    try:
        if source_api == 'createOrder':
            operation = get_customer_order_param('operation', customer_order_params)
            step = get_customer_order_param('step', customer_order_params)

            customer_id = get_customer_order_param('Cust_Key', customer_order_params)
            vnf_type = get_customer_order_param('vnf_type', customer_order_params)
            rt_left = get_customer_order_param('rt-left', customer_order_params)
            rt_right = get_customer_order_param('rt-right', customer_order_params)
            rt_mgmt = get_customer_order_param('rt-mgmt', customer_order_params)

            if rt_left or rt_right or rt_mgmt is None:
                # Send back NSO error
                _exit('FAILURE')

            # Previous operation = createService
            order_type = get_order_item('createService', order_json)

            if order_type == 'createService':
                service_id = get_order_item('createService', order_json)['id']
                service_name = get_order_item('createService', order_json)['name']

                if order_status == 'COM':
                    pass
                elif order_status == 'SUBACT':
                    # Is SUBACT a possible value? to check
                    pass
                else:
                    # No rollback required here as we're at the first step, notify nso immidiatly
                    # TODO notify NSO
                    _exit('FAILURE')

                cur = dbman.query('''SELECT * FROM cpower WHERE customer_key=123''')
                if cur.rowcount > 0:
                    # The request is to add a new VNF to an existing one, what to do?
                    pass
                else:
                    customer_row = (customer_id,)
                    ntw_service_row = (service_id,
                                       service_name,
                                       customer_id,
                                       rt_left,
                                       rt_right,
                                       'rt-mgmt',
                                       vnf_type,
                                       None)
                    try:
                        dbman.save_customer(customer_row)
                        dbman.save_network_service(ntw_service_row)
                        logging.info('Data successfully added to cpower table: %s' % ntw_service_row)
                    except sqlite3.IntegrityError:
                        dbman.rollback()
                        logging.error('Could not insert the following data to cpower table %s.' % ntw_service_row)
                        _exit('FAILURE')

                file_name = 'filename.json'
                try:
                    json_data = get_json_from_file(file_name)
                except IOError:
                    logging.error('No such file or directory: %s' % file_name)
                    _exit('FAILURE')

                # Put step2 in customer order param (in operation tag)
                if vnf_type == 'csr1000':
                    # TODO substitute attributes in JSON file according to vnf_type
                    pass
                elif vnf_type == 'fortinet':
                    # TODO substitute attributes in JSON file according to vnf_type
                    pass
                try:
                    ecmutil.create_order(json_data)
                except ECMOrderResponseError as re:
                    logging.error('ECM error response.')
                except ECMConnectionError as ce:
                    logging.error('Impossible to contact ECM.')
                else:
                    dbman.commit()
            elif order_type == 'deleteService':
                # TODO
                pass
        elif source_api == 'deployOvfPackage':
            # TODO
            pass
        else:
            logging.info('%s operation not handled' % source_api)

        _exit('SUCCESS')
    except Exception as e:
        logging.exception('Exception encountered during stript execution.')
        _exit('FAILURE')


if __name__ == '__main__':
    main()
else:
    print 'sorry :('
