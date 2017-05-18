#!/usr/bin/env python 

import sqlite3
import os
import sys
import json
import logging
import ECMUtil as ecm_util
import NSOUtil as nso_util
from DBManager import DBManager
from ECMException import *
import config as c

GENERIC_ERROR = '100'
REQUEST_ERROR = '200'
NETWORK_ERROR = '300'

def get_empty_param(**kargs):
    for name, value in kargs.items():
        if not value or value is None:
            return name
    return None


def get_env_var(var_name):
    """Return the value of the given environment variable."""
    if var_name in os.environ:
        return os.environ[var_name]
    return None


def get_custom_order_param(s, json_data):
    """Returns the customerOrderParam value that matches the given name s. None is returned if the is no matching 
    customerOrderParam. """
    for custom_param in json_data:
        if s == custom_param['tag']:
            return custom_param['value']
    return None


def get_custom_input_params(order_item_name, json_data_compl):
    order_item = get_order_item(order_item_name, json_data_compl)
    return order_item['customInputParams']


def get_custom_input_param(param_name, json_data):
    for custom_input_param in json_data:
        if param_name == custom_input_param['tag']:
            return custom_input_param['value']
    return None


def get_order_item(order_item_name, json_data):
    """Returns a dictionary representing the single item orderItem that matches order_item_name from the ECM getOrder 
    JSON response. None is returned if there is no matching orderItem."""
    order_items = json_data['data']['order']['orderItems']
    for order_item in order_items:
        item_name = order_item.keys()[0]
        if item_name == order_item_name:
            return order_item[item_name]
    return None


def deserialize_json_file(file_name):
    """Returns a dictionary object from a file JSON"""
    with open(file_name) as f:
        data = json.load(f)
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

    empty_env_var = get_empty_param(order_id=order_id, source_api=source_api, order_status=order_status)
    if empty_env_var is not None:
        logging.error("Environment variable '%s' not found or empty." % empty_env_var)
        _exit('FAILURE')

    dbman = DBManager('cpower.db')


    try:
        # Getting ECM order
        logging.info("Environments variables found: ORDER_ID='%s' SOURCE_API='%s' ORDER_STATUS='%s'"
                     % (order_id, source_api, order_status))
        order_resp = ecm_util.get_order(order_id)
        logging.info("Response received: %s" % order_resp.status_code)
        logging.debug(order_resp.text)
    except ECMOrderResponseError as oe:
        logging.error('ECM response status code not equal to 2**.')
        _exit('FAILURE')
    except ECMConnectionError as ce:
        logging.exception('Unable to connect to ECM.')
        _exit('FAILURE')

    order_json = json.loads(order_resp.text)

    try:
        if source_api == 'createOrder':
            # Getting customer order params from response
            custom_order_params = order_json['data']['order']['customOrderParams'] # check if it generates exception

            if get_order_item('createService', order_json) is not None:
                customer_id = get_custom_order_param('Cust_Key', custom_order_params)
                vnf_type = get_custom_order_param('vnf_type', custom_order_params)
                rt_left = get_custom_order_param('rt-left', custom_order_params)
                rt_right = get_custom_order_param('rt-right', custom_order_params)
                rt_mgmt = get_custom_order_param('rt-mgmt', custom_order_params)

                nso_error_notification = {'operation': 'createService', 'result': 'failure', 'customer-key': customer_id}

                if order_status == 'ERR':
                    nso_util.notify_nso(nso_error_notification)
                    _exit('FAILURE')

                empty_cop = get_empty_param(customer_id=customer_id, vnf_type=vnf_type, rt_left=rt_left,
                                            rt_right=rt_right,
                                            rt_mgmt=rt_mgmt)

                if empty_cop is not None:
                    error_message = "Custom order parameter '%s' not found or empty." % empty_cop
                    logging.error(error_message)
                    params = {'operation': 'genericError', 'customer-key': customer_id, 'error-code': REQUEST_ERROR,
                              'error-message': error_message}
                    nso_util.notify_nso(params)
                    _exit('FAILURE')

                service_id = get_order_item('createService', order_json)['id']
                service_name = get_order_item('createService', order_json)['name']

                try:
                    dbman.save_customer((customer_id, customer_id + '_name'))
                except sqlite3.IntegrityError:
                    # Customer already in DB, it's ok.
                    pass

                ntw_service_row = (service_id, customer_id, service_name, rt_left, rt_right, rt_mgmt)
                try:
                    dbman.save_network_service(ntw_service_row)
                    logging.info('Network Service \'%s\' successfully stored to DB.' % service_id)
                except sqlite3.IntegrityError:
                    logging.error('Could not store data to DB.')
                    _exit('FAILURE')

                if vnf_type == 'csr1000':
                    ovf_package_id = c.ovf_package_dpi_1
                elif vnf_type == 'fortinet':
                    ovf_package_id = c.ovf_package_fortinet_1
                else:
                    logging.error('VNF Type %s not supported' % vnf_type)
                    _exit('FAILURE')

                deploy_ovf_package_file = './json/deploy_ovf_package.json'
                try:
                    ovf_package_json = deserialize_json_file(deploy_ovf_package_file)
                    ovf_package_json['tenantName'] = c.ecm_tenant_name
                    ovf_package_json['vdc']['id'] = c.ecm_vdc_id
                    ovf_package_json['ovfPackage']['namePrefix'] = customer_id + '-'
                except IOError:
                    logging.error('No such file or directory: %s' % deploy_ovf_package_file)
                    _exit('FAILURE')

                try:
                    ecm_util.deploy_ovf_package(ovf_package_id, ovf_package_json)
                except ECMOrderResponseError as re:
                    # TODO notify NSO
                    logging.error('ECM error response.')
                    _exit('FAILURE')
                except ECMConnectionError as ce:
                    # TODO notify NSO
                    _exit('FAILURE')
            elif get_order_item('createVlink', order_json) is not None:
                # TODO
                pass
            else:
                logging.error('Custmor workflow ended up in a inconsistent state, please check the logs.')
                _exit('FAILURE')
        elif source_api == 'modifyService':
            custom_input_params = get_custom_input_params('modifyService', order_json)
            get_custom_input_param('vnf_type', custom_input_params) # i.e.: How to get customInputParam
            # TODO
        elif source_api == 'deployOvfPackage':
            # TODO
            pass
        elif source_api == 'modifyVapp':
            # TODO
            pass
        elif source_api == 'deleteService':
            # TODO
            pass
        else:
            logging.info('%s operation not handled' % source_api)

        _exit('SUCCESS')
    except Exception as e: # Fix this
        logging.exception('Something went wrong during script execution.')
        _exit('FAILURE')


if __name__ == '__main__':
    main()
else:
    print 'sorry :('
