#!/usr/bin/env python 

import sqlite3
import os
import sys
import json
from logging.handlers import *
import logging
import ecm_util as ecm_util
import nso_util as nso_util
from db_manager import DBManager
from ecm_exception import *
from nso_exception import *
import config as c

logger = logging.getLogger('cpower')

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
    order_item = get_order_items(order_item_name, json_data_compl)
    return order_item[0]['customInputParams']


def get_custom_input_param(param_name, json_data):
    for custom_input_param in json_data:
        if param_name == custom_input_param['tag']:
            return custom_input_param['value']
    return None


def get_order_items(order_item_name, json_data):
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
    """Returns a dictionary object from a JSON file"""
    with open(file_name) as f:
        data = json.load(f)
    return data


def get_ovf_package_id(vnf_type):
    if vnf_type == 'csr1000':
        return c.ovf_package_dpi_1
    elif vnf_type == 'fortinet':
        return c.ovf_package_fortinet_1
    else:
        raise VnfTypeException

def _exit(exit_mess):
    e = {'SUCCESS': 0, 'FAILURE': 1}
    logger.info('End of script execution - %s' % exit_mess)
    try:
        sys.exit(e[exit_mess])
    except (NameError, KeyError):
        sys.exit(1)


def main():
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    logger.setLevel(logging.DEBUG)
    if not os.path.exists('log'):
        os.makedirs('log')
    handler = RotatingFileHandler('log/cpower.log', maxBytes=10*1000*1000, backupCount=10)
    handler.setFormatter(formatter)
    logger.addHandler(handler)

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

    dbman = DBManager('cpower.db')

    try:
        logger.info("Environments variables found: ORDER_ID='%s' SOURCE_API='%s' ORDER_STATUS='%s'"
                     % (order_id, source_api, order_status))
        # Getting ECM order using the ORDER_ID env var
        order_resp = ecm_util.invoke_ecm_api(order_id, c.ecm_service_api_orders, 'GET')
    except ECMOrderResponseError as oe:
        logger.error('ECM response status code not 200.')
        _exit('FAILURE')
    except ECMConnectionError as ce:
        logger.exception('Unable to connect to ECM.')
        _exit('FAILURE')

    order_json = json.loads(order_resp.text)

    try:
        if source_api == 'createOrder':
            # Getting customer order params from getOrder response
            create_order_cop = order_json['data']['order']['customOrderParams'] # check if it generates exception

            # Checking if order type is createService
            if get_order_items('createService', order_json) is not None:
                customer_id = get_custom_order_param('Cust_Key', create_order_cop)
                vnf_type = get_custom_order_param('vnf_type', create_order_cop)
                rt_left = get_custom_order_param('rt-left', create_order_cop)
                rt_right = get_custom_order_param('rt-right', create_order_cop)
                rt_mgmt = get_custom_order_param('rt-mgmt', create_order_cop)

                operation_error = {'operation': 'createService', 'result': 'failure', 'customer-key': customer_id}
                workflow_error = {'operation': 'genericError', 'customer-key': customer_id}

                if order_status == 'ERR':
                    logger.error(order_json['data']['order']['orderMsgs'])
                    nso_util.notify_nso(operation_error)
                    _exit('FAILURE')

                # Checking if the needed custom order params are empty
                empty_cop = get_empty_param(customer_id=customer_id, vnf_type=vnf_type, rt_left=rt_left,
                                            rt_right=rt_right,
                                            rt_mgmt=rt_mgmt)

                if empty_cop is not None:
                    error_message = "Custom order parameter '%s' not found or empty." % empty_cop
                    logger.error(error_message)
                    workflow_error['error-code'] = REQUEST_ERROR
                    workflow_error['error-message'] = error_message
                    nso_util.notify_nso(workflow_error)
                    _exit('FAILURE')

                service_id = get_order_items('createService', order_json)[0]['id']
                service_name = get_order_items('createService', order_json)[0]['name']

                # We got everything we need to proceed:
                # Saving customer and network service info to DB. A check is not needed as NSO should send a
                # createService only in case of first VNF creation. This means there should not be customer and service
                # already.
                try:
                    dbman.save_customer((customer_id, customer_id + '_name'))
                except sqlite3.IntegrityError:
                    # Customer already in DB, it shouldn't be possible for createService operation
                    pass

                ntw_service_row = (service_id, customer_id, service_name, rt_left, rt_right, rt_mgmt, vnf_type, '', '', '')
                dbman.save_network_service(ntw_service_row)
                logger.info('Network Service \'%s\' successfully stored to DB.' % service_id)

                # Loading the right ovf package id depending on the requested VNF type.
                # It is loaded the ovf package 1 as we are in the 'createService' (meaning that the first VNF for the
                # service is being requested
                try:
                    ovf_package_id = get_ovf_package_id(vnf_type)
                except VnfTypeException:
                    error_message = 'VNF Type \'%s\' is not supported.' % vnf_type
                    logger.error(error_message)
                    workflow_error['error-code'] = REQUEST_ERROR
                    workflow_error['error-message'] = error_message
                    nso_util.notify_nso(workflow_error)
                    _exit('FAILURE')

                deploy_ovf_package_file = './json/deploy_ovf_package.json'
                ovf_package_json = deserialize_json_file(deploy_ovf_package_file)
                ovf_package_json['tenantName'] = c.ecm_tenant_name
                ovf_package_json['vdc']['id'] = c.ecm_vdc_id
                ovf_package_json['ovfPackage']['namePrefix'] = customer_id + '-'

                try:
                    ecm_util.deploy_ovf_package(ovf_package_id, ovf_package_json)
                except (ECMConnectionError, ECMOrderResponseError):
                    # TODO notify NSO
                    logger.error('Unable to contact ECM APIs northbound interface.')
                    operation_error['operation'] = 'createVnf'
                    nso_util.notify_nso(operation_error)
                    _exit('FAILURE')
            elif get_order_items('createVlink', order_json) is not None:
                # TODO
                pass
            else:
                logger.error('Custmor workflow ended up in a inconsistent state, please check the logs.')
                _exit('FAILURE')
        elif source_api == 'deployOvfPackage':
            # OVF structure 1 createVapp, 1 createVm, 3 createVmVnic, 0/2 createVn
            customer_id = get_order_items('createVm', order_json)[0]['name'].split('-')[0]

            operation_error = {'operation': 'createVnf', 'result': 'failure', 'customer-key': customer_id}
            workflow_error = {'operation': 'genericError', 'customer-key': customer_id}

            if order_status == 'ERR':
                logger.error(order_json['data']['order']['orderMsgs'])
                nso_util.notify_nso(operation_error)
                _exit('FAILURE')

            # Getting VNF, VNs, VMVNICS detail
            vnf_id = get_order_items('createVapp', order_json)[0]['id']
            vm_id = get_order_items('createVm', order_json)[0]['id']
            vm_name = get_order_items('createVm', order_json)[0]['name']

            vns = get_order_items('createVn', order_json)
            if vns is not None:
                for vn in vns:
                    if 'left' in vn['name']:
                        vn_left = vn
                    elif 'right' in vn['name']:
                        vn_right = vn

            vmvnics = get_order_items('createVmVnic', order_json)
            vmvnic_ids = []
            vmvnic_names = []
            for vmvnic in vmvnics:
                if 'mgmt' not in vmvnic['name']:
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
            vm_row = (vm_id, vnf_id, vm_name, vmvnic_ids[0], vmvnic_names[0], '', vmvnic_ids[1], vmvnic_names[1], '')
            dbman.save_vm(vm_row)

            # Modifying service
            modify_service_file = './json/modify_service.json'
            modify_service_json = deserialize_json_file(modify_service_file)
            modify_service_json['vapps'][0]['id'] = vnf_id
            modify_service_json['customInputParams'].append({"tag":"Cust_Key", "value":customer_id})

            try:
                service_resp = ecm_util.invoke_ecm_api(network_service_id, c.ecm_service_api_services, 'PUT', modify_service_json)
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
            customer_id = get_custom_input_param('Cust_Key', get_custom_input_params('modifyService', order_json))

            operation_error = {'operation': 'createService', 'result': 'failure', 'customer-key': customer_id}
            workflow_error = {'operation': 'genericError', 'customer-key': customer_id}

            if order_status == 'ERR':
                nso_util.notify_nso(operation_error)
                _exit('FAILURE')

            if get_custom_input_param('source', get_custom_input_params('modifyService', order_json)) == 'workflow':
                service = get_order_items('modifyService', order_json)[0]
                service_id = service['id']
                vnf_id = service['vapps'][0]['id']

                # Associate service network - vnf into DB
                dbman.query('UPDATE vnf SET ntw_service_binding=? WHERE vnf_id=?', ('YES', vnf_id))

                # Getting VM id from DB, and get vimObjectId from ECM (/vms API)
                dbman.query('SELECT * FROM vm WHERE vnf_id=?', (vnf_id, ))
                row = dbman.fetchone()
                vm_id = row['vm_id']
                vm_vnic1_id = row['vm_vnic1_id']
                vm_vnic1_name = row['vm_vnic1_name']
                vm_vnic2_id = row['vm_vnic2_id']
                vm_vnic2_name = row['vm_vnic2_name']

                # Getting vmvnics /vmvnics/<vmvnic_id> detail in order to get and store vmvnic_vimobject_id
                resp = ecm_util.invoke_ecm_api(vm_vnic1_id, c.ecm_service_api_vmvnics, 'GET')
                vmvnics_json = json.loads(resp.text)
                vm_vnic1_vimobject_id = vmvnics_json['data']['vmVnic']['vimObjectId']

                resp = ecm_util.invoke_ecm_api(vm_vnic2_id, c.ecm_service_api_vmvnics, 'GET')
                vmvnics_json = json.loads(resp.text)
                vm_vnic2_vimobject_id = vmvnics_json['data']['vmVnic']['vimObjectId']

                dbman.query('UPDATE vm SET vm_vnic1_vimobject_id=?,vm_vnic2_vimobject_id=? WHERE vm_id=?',
                            (vm_vnic1_vimobject_id, vm_vnic2_vimobject_id, vm_id))

                #Checking if VLinks already exists
                dbman.query('SELECT * FROM network_service WHERE customer_id=?', (customer_id, ))
                row = dbman.fetchone()
                vlink_id = row['vlink_id']

                if not vlink_id:
                    # Creating VLinks and CPs
                    vlink_cp_json = deserialize_json_file('json/create_vlink_cp.json')
                    vlink_cp_json['orderItems'][0]['createVlink']['name'] = customer_id + '_policy'
                    vlink_cp_json['orderItems'][0]['createVlink']['service']['id'] = service_id

                    extensions_input_create = deserialize_json_file('json/extensions_input_create.json')
                    # TODO filling ex inputs
                    vlink_cp_json['orderItems'][0]['createVlink']['customInputParams'][0]['value'] = str(extensions_input_create)

                    vlink_cp_json['orderItems'][1]['createCp']['name'] = customer_id + '_VN_LEFT'
                    vlink_cp_json['orderItems'][1]['createCp']['address'] = vm_vnic1_name
                    vlink_cp_json['orderItems'][1]['createCp']['vapp']['id'] = vnf_id

                    vlink_cp_json['orderItems'][2]['createCp']['name'] = customer_id + '_VN_RIGHT'
                    vlink_cp_json['orderItems'][2]['createCp']['address'] = vm_vnic2_name
                    vlink_cp_json['orderItems'][2]['createCp']['vapp']['id'] = vnf_id
                    try:
                        ecm_util.invoke_ecm_api(c.ecm_service_api_orders, 'POST', vlink_cp_json)
                    except (ECMOrderResponseError, ECMConnectionError):
                        # TODO notify NSO
                        _exit('FAILURE')
                else:
                    # Modifying... TODO
                    modify_vlink_json = deserialize_json_file('json/modify_vlink.json')
                    extensions_input_modify = deserialize_json_file('json/extensions_input_modify.json')
                    # TODO filliong ex inputs
                    modify_vlink_json['customInputParams'][0]['value'] = str(extensions_input_modify)
                    try:
                        ecm_util.invoke_ecm_api(vlink_id, c.ecm_service_api_vlinks, 'PUT', modify_vlink_json)
                    except (ECMOrderResponseError, ECMConnectionError):
                        # TODO notify NSO
                        _exit('FAILURE')


            else:
                modify_service_cip = get_custom_input_params('modifyService', order_json)

                customer_id = get_custom_input_param('Cust_Key', modify_service_cip)
                vnf_type = get_custom_input_param('vnf_type', modify_service_cip)

                # Checking if the needed custom order params are empty
                empty_cop = get_empty_param(customer_id=customer_id, vnf_type=vnf_type)
                #TODO continue
                pass
        else:
            logger.info('%s operation not handled' % source_api)

        _exit('SUCCESS')
    except Exception as e: # Fix this
        dbman.rollback()
        logger.exception('Something went wrong during script execution.')
        _exit('FAILURE')


if __name__ == '__main__':
    main()
else:
    print 'sorry :('
