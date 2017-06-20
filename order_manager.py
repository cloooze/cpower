#!/usr/bin/env python

import json
from ecm_exception import *
from nso_exception import *
import os
import config as c
import logging
import sys

logger = logging.getLogger('cpower')


class OrderManager(object):

    def execute(self):
        raise NotImplementedError()

    def get_empty_param(**kargs):
        for name, value in kargs.items():
            if not value or value is None:
                return name
        return None

    def get_env_var(self, var_name):
        """Return the value of the given environment variable."""
        if var_name in os.environ:
            return os.environ[var_name]
        return None

    def get_custom_order_param(self, s, json_data):
        """Returns the customerOrderParam value that matches the given name s. None is returned if the is no matching
        customerOrderParam. """
        for custom_param in json_data:
            if s == custom_param['tag']:
                return custom_param['value']
        return None

    def get_custom_input_params(self, order_item_name, json_data_compl):
        order_item = self.get_order_items(order_item_name, json_data_compl)
        return order_item[0]['customInputParams']

    def get_custom_input_param(param_name, json_data):
        for custom_input_param in json_data:
            if param_name == custom_input_param['tag']:
                return custom_input_param['value']
        return None

    def get_order_items(self, order_item_name, json_data):
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

    def load_json_file(self, file_name):
        """Returns a dictionary object from a JSON file"""
        with open(file_name) as f:
            data = json.load(f)
        return data

    # Deprecated
    def get_ovf_package_id_v2(self, vnf_type):
        if vnf_type == 'csr1000':
            return c.ovf_package_dpi_1
        elif vnf_type == 'fortinet':
            return c.ovf_package_fortinet_1
        else:
            raise VnfTypeException

    def get_ovf_package_id(self, vnf_type, operation):
        json = self.load_json_file('json/ovf_packages_mapping.json')
        for i in json:
            if i['type'] == vnf_type:
                for v in i['map']:
                    if v['operation'] == operation:
                        return v['id']
        raise VnfTypeException

    @staticmethod
    def exit(exit_mess):
        e = {'SUCCESS': 0, 'FAILURE': 1}
        logger.info('End of script execution - %s' % exit_mess)
        try:
            sys.exit(e[exit_mess])
        except (NameError, KeyError):
            sys.exit(1)