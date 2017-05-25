#!/usr/bin/env python 

import sqlite3
import os
import sys
import json
import logging
import ecm_util as ecm_util
import nso_util as nso_util
from db_manager import DBManager
from ecm_exception import *
import config as c

INTERNAL_ERROR = '100'
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
    r = []
    order_items = json_data['data']['order']['orderItems']
    for order_item in order_items:
        item_name = order_item.keys()[0]
        if item_name == order_item_name:
            r.append(order_item[item_name])
    if len(r) > 0:
        return tuple(r)
    else:
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

    # Getting env var set by ECMSID
    order_id = get_env_var('ECM_PARAMETER_ORDERID')
    source_api = get_env_var('ECM_PARAMETER_SOURCEAPI')
    order_status = get_env_var('ECM_PARAMETER_ORDERSTATUS')

    # Checking if some of the env var are empty
    empty_env_var = get_empty_param(order_id=order_id, source_api=source_api, order_status=order_status)
    if empty_env_var is not None:
        logging.error("Environment variable '%s' not found or empty." % empty_env_var)
        _exit('FAILURE')

    dbman = DBManager('cpower.db')

    try:
        logging.info("Environments variables found: ORDER_ID='%s' SOURCE_API='%s' ORDER_STATUS='%s'"
                     % (order_id, source_api, order_status))
        # Getting ECM order using the ORDER_ID env var
        order_resp = ecm_util.invoke_ecm_api(order_id, c.ecm_service_api_orders, 'GET')
    except ECMOrderResponseError as oe:
        logging.error('ECM response status code not equal to 2**.')
        _exit('FAILURE')
    except ECMConnectionError as ce:
        logging.exception('Unable to connect to ECM.')
        _exit('FAILURE')

    order_json = json.loads(order_resp.text)

    try:
        if source_api == 'createOrder':
            # Getting customer order params from getOrder response
            custom_order_params = order_json['data']['order']['customOrderParams'] # check if it generates exception

            # Checking if order type is createService
            if get_order_item('createService', order_json) is not None:
                customer_id = get_custom_order_param('Cust_Key', custom_order_params)
                vnf_type = get_custom_order_param('vnf_type', custom_order_params)
                rt_left = get_custom_order_param('rt-left', custom_order_params)
                rt_right = get_custom_order_param('rt-right', custom_order_params)
                rt_mgmt = get_custom_order_param('rt-mgmt', custom_order_params)

                operation_error = {'operation': 'createService', 'result': 'failure', 'customer-key': customer_id}
                workflow_error = {'operation': 'genericError', 'customer-key': customer_id}

                if order_status == 'ERR':
                    logging.error(order_json['data']['order']['orderMsgs'])
                    nso_util.notify_nso(operation_error)
                    _exit('FAILURE')

                # Checking if the needed custom order params are empty
                empty_cop = get_empty_param(customer_id=customer_id, vnf_type=vnf_type, rt_left=rt_left,
                                            rt_right=rt_right,
                                            rt_mgmt=rt_mgmt)

                if empty_cop is not None:
                    error_message = "Custom order parameter '%s' not found or empty." % empty_cop
                    logging.error(error_message)
                    workflow_error['error-code'] = REQUEST_ERROR
                    workflow_error['error-message'] = error_message
                    nso_util.notify_nso(workflow_error)
                    _exit('FAILURE')

                service_id = get_order_item('createService', order_json)[0]['id']
                service_name = get_order_item('createService', order_json)[0]['name']

                # We got everything we need to proceed:
                # Saving customer and network service info to DB. A check is not needed as NSO should send a
                # createService only in case of first VNF creation. This means there should not be customer and service
                # already.
                try:
                    dbman.save_customer((customer_id, customer_id + '_name'))
                except sqlite3.IntegrityError:
                    # Customer already in DB, it's ok.
                    pass

                ntw_service_row = (service_id, customer_id, service_name, rt_left, rt_right, rt_mgmt, vnf_type, '', '', '')
                dbman.save_network_service(ntw_service_row)
                logging.info('Network Service \'%s\' successfully stored to DB.' % service_id)

                # Loading the right ovf package id depending on the requested VNF type.
                # It is loaded the ovf package 1 as we are in the 'createService' (meaning that the first VNF for the
                # service is being requested
                if vnf_type == 'csr1000':
                    ovf_package_id = c.ovf_package_dpi_1
                elif vnf_type == 'fortinet':
                    ovf_package_id = c.ovf_package_fortinet_1
                else:
                    error_message = 'VNF Type \'%s\' is not supported.' % vnf_type
                    logging.error(error_message)
                    workflow_error['error-code'] = REQUEST_ERROR
                    workflow_error['error-message'] = error_message
                    nso_util.notify_nso(workflow_error)
                    _exit('FAILURE')

                deploy_ovf_package_file = './json/deploy_ovf_package.json'
                try:
                    ovf_package_json = deserialize_json_file(deploy_ovf_package_file)
                    ovf_package_json['tenantName'] = c.ecm_tenant_name
                    ovf_package_json['vdc']['id'] = c.ecm_vdc_id
                    ovf_package_json['ovfPackage']['namePrefix'] = customer_id + '-'
                except IOError:
                    logging.error('No such file or directory: %s' % deploy_ovf_package_file)
                    workflow_error['error-code'] = INTERNAL_ERROR
                    workflow_error['error-message'] = 'Internal custom workflow error.'
                    nso_util.notify_nso(workflow_error)
                    _exit('FAILURE')

                try:
                    ecm_util.deploy_ovf_package(ovf_package_id, ovf_package_json)
                except (ECMConnectionError, ECMOrderResponseError):
                    # TODO notify NSO
                    logging.error('Unable to contact ECM APIs northbound interface.')
                    operation_error['operation'] = 'createVnf'
                    nso_util.notify_nso(operation_error)
                    _exit('FAILURE')
            elif get_order_item('createVlink', order_json) is not None:
                # TODO
                pass
            else:
                logging.error('Custmor workflow ended up in a inconsistent state, please check the logs.')
                _exit('FAILURE')
        elif source_api == 'deployOvfPackage':
            # OVF structure 1 createVapp, 1 createVm, 3 createVmVnic, 0/2 createVn
            customer_id = get_order_item('createVm', order_json)[0]['name'].split('-')[0]

            operation_error = {'operation': 'createVnf', 'result': 'failure', 'customer-key': customer_id}
            workflow_error = {'operation': 'genericError', 'customer-key': customer_id}

            if order_status == 'ERR':
                logging.error(order_json['data']['order']['orderMsgs'])
                nso_util.notify_nso(operation_error)
                _exit('FAILURE')

            # Getting VNF, VNs, VMVNICS detail
            vnf_id = get_order_item('createVapp', order_json)[0]['id']
            vm_id = get_order_item('createVm', order_json)[0]['id']

            vns = get_order_item('createVn', order_json)
            if vns is not None:
                for vn in vns:
                    if 'left' in vn['name']:
                        vn_left = vn
                    elif 'right' in vn['name']:
                        vn_right = vn

            vmvnics = get_order_item('createVmVnic', order_json)
            vmvnic_ids = []
            vmvnic_names = []
            for vmvnic in vmvnics:
                vmvnic_ids.append(vmvnic['id'])
                vmvnic_names.append(vmvnic['name'])

            # Getting ntw service id and vnftype for this customer (assuming that 1 customer can have max 1 ntw service)
            dbman.query('SELECT ntw_service_id, vnf_type FROM network_service ns WHERE ns.customer_id = ?', (customer_id, ))
            row = dbman.fetchone()
            network_service_id = row['ntw_service_id']
            vnf_type = row['vnf_type'] # ???

            # Checking if there is already a VNF for this network service
            dbman.query('SELECT * FROM vnf WHERE ntw_service_id=?', (network_service_id, ))
            r = dbman.fetchone()
            if r is not None:
                # Move vnf_position to 2
                dbman.query('UPDATE vnf SET vnf_position=? WHERE vnf.ntw_service_id=?', ('2', network_service_id), False)
            else:
                # Saving VN group info to db
                vn_left_resp = ecm_util.invoke_ecm_api(vn_left['id'], c.ecm_service_api_vns, 'GET')
                vn_left_resp_json = json.loads(vn_left_resp.text)
                vn_right_resp = ecm_util.invoke_ecm_api(vn_right['id'], c.ecm_service_api_vns, 'GET')
                vn_right_resp_json = json.loads(vn_right_resp.text)

                vn_group_row = (vnf_id, vn_left['id'], vn_left['name'], vn_left_resp_json['data']['vn']['vimObjectId'],
                                vn_right['id'], vn_right['name'], vn_right_resp_json['data']['vn']['vimObjectId'])

                dbman.save_vn_group(vn_group_row, False)

            # Saving VNF info to db
            vnf_row = (vnf_id, network_service_id, vnf_type, '1', 'NO')
            dbman.save_vnf(vnf_row, False)

            # Saving VM info to db
            vm_row = (vm_id, vnf_id, vmvnic_ids[0], vmvnic_names[0], '', vmvnic_ids[1], vmvnic_names[1], '')
            dbman.save_vm(vm_row)

            # Modifying service
            modify_service_file = './json/modify_service.json'
            modify_service_json = deserialize_json_file(modify_service_file)
            modify_service_json['vapps'][0]['id'] =  vnf_id

            try:
                ecm_util.invoke_ecm_api(network_service_id, c.ecm_service_api_services, 'PUT', modify_service_json)
            except (ECMOrderResponseError, ECMConnectionError):
                # TODO notify NSO What to Do here??
                _exit('FAILURE')

            dbman.commit()
        elif source_api == 'modifyVapp':
            # TODO
            pass
        elif source_api == 'deleteService':
            # TODO
            pass
        elif source_api == 'modifyService':
            operation_error = {'operation': 'createService', 'result': 'failure', 'customer-key': customer_id}
            workflow_error = {'operation': 'genericError', 'customer-key': customer_id}

            if order_status == 'ERR':
                nso_util.notify_nso(operation_error)
                _exit('FAILURE')

            if get_custom_input_param('source', get_custom_input_params('modifyService', order_json)) == 'workflow':
                service = get_order_item('modifyService', order_json)
                service_id = service['id']
                vnf_id = service['vapss'][0]['id']

                # Associate service network - vnf into DB
                dbman.query('UPDATE vnf SET ntw_service_binding=? WHERE vnf_id=?', ('YES', vnf_id))

                # Getting VM id from DB, and get vimObjectId from ECM (/vms API)
                dbman.get_vnf(vnf_id)
                vm_id = dbman.fetchone()['vm_id']

                resp = ecm_util.invoke_ecm_api(vm_id, 'GET', c.ecm_service_api_vms)
                vm_json = json.loads(resp.text)

                vmvnics_detail = {"name": vm_json['data']['vm']['vmVnics'][0]['name'][-5:],
                            "id": vm_json['data']['vm']['vmVnics'][0]['id'],
                            "name": vm_json['data']['vm']['vmVnics'][1]['name'][-5:],
                            "id": vm_json['data']['vm']['vmVnics'][0]['id']}


                # Checking if vmvnics


            else:
                # TODO implement function
                pass
        else:
            logging.info('%s operation not handled' % source_api)

        _exit('SUCCESS')
    except Exception as e: # Fix this
        dbman.rollback()
        logging.exception('Something went wrong during script execution.')
        _exit('FAILURE')


if __name__ == '__main__':
    main()
else:
    print 'sorry :('
