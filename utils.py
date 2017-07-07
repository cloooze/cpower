#!/usr/bin/env python

import json
from nso_exception import *
import os
import datetime


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


def get_custom_order_param(tag, json_data):
    """Returns the customerOrderParam value that matches the given name s. None is returned if the is no matching
    customerOrderParam. """
    for custom_param in json_data:
        if tag == custom_param['tag']:
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


def get_order_items(order_item_name, json_data, n=None):
    """Returns a dictionary representing the items orderItem that matches order_item_name from the ECM getOrder
    JSON response. None is returned if there is no matching orderItem. If n is specified the returning tuple is
    truncated."""
    r = []
    order_items = json_data['data']['order']['orderItems']
    for order_item in order_items:
        item_name = order_item.keys()[0]
        if item_name == order_item_name:
            r.append(order_item[item_name])
    if len(r) > 0:
        return tuple(r) if n is None else tuple(r)[:n][0]
    else:
        return None

'''
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
'''


def load_json_file(file_name):
    """Returns a dictionary object from a JSON file"""
    with open(file_name) as f:
        data = json.load(f)
    return data


def get_ovf_package_id(vnf_type, operation):
    json = load_json_file('json/ovf_packages_mapping.json')
    for i in json:
        if i['type'] == vnf_type:
            for v in i['map']:
                if v['operation'] == operation:
                    return v['id']
    raise VnfTypeException


def get_now(format=None):
    if format is None:
        return datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3]
    else:
        return datetime.datetime.now().strftime(format)[:-3]


# CREATE ORDER JSON UTILS

def get_cop(tag, value):
    j = dict(
        {
            'tag': tag,
            'value': value
        }
    )
    return j


def get_create_vapp(order_item_id, vapp_name, vdc_id, vim_zone_name):
    j = dict(
        {
            'orderItemId': order_item_id,
            'creteVapp': {
                'name': vapp_name,
                'vdc': {
                    'id': vdc_id
                },
                'vimZoneName': vim_zone_name
            }
        }
    )
    return j


def get_create_vm(order_item_id, vdc_id, vm_name, image_name, vmhd_name, order_item_ref_vapp):
    j = dict(
        {
            'orderItemId': order_item_id,
            'creteVm': {
                'vdc': {
                    'id': vdc_id
                },
                'name': vm_name,
                'bootSource': {
                    'imageName': image_name
                },
                'vmhdName': vmhd_name,
                'vapp': {
                    'orderItemRef': order_item_ref_vapp
                }
            }
        }

    )
    return j


def get_create_vn(order_item_id, vdc_id, vn_name, vn_description):
    j = dict(
        {
            'orderItemId': order_item_id,
            'createVn': {
                'vdc': {
                    'id': vdc_id
                },
                'name': vn_name,
                'description': vn_description,
                'ipVersion': 'IPv4',
                'cidrSize': '30',
                'enabled': 'true',
                'dhcpEnabled': 'true',
                'category': 'L3'
            }
        }
    )
    return j


def get_create_vmvnic(order_item_id, order_item_ref_vn, order_item_ref_vm, vmvnic_description, vn_id=None):
    j = dict(
        {
            'orderItemId': order_item_id,
            "vn":
                ({'orderItemRef': order_item_ref_vn} if vn_id is None else {'vn_id': vn_id})
            ,
            "vm": {
                "orderItemRef": order_item_ref_vm
            },
            "description": vmvnic_description
        }
    )
    return j