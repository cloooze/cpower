#!/usr/bin/env python 

import unittest
import nso_util as NSOUtil
import config as c
from nso_exception import *


class NSOUtilTest(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_get_nso_json_data(self):
        j = {'customer-key': '1234', 'vnf-id': '6666', 'mgmt-ip': '7777:77', 'cust-ip': '8888:88', 'ntw-ip': '9999:99'}
        j_data = NSOUtil.get_nso_json_data(j)
        self.assertEqual('1234', j_data['cpwr:vnfconfig']['customer-key'])
        self.assertEqual('6666', j_data['cpwr:vnfconfig']['vnf-id'])
        self.assertEqual('7777:77', j_data['cpwr:vnfconfig']['vnf-info']['mgmt-ip'])
        self.assertEqual('8888:88', j_data['cpwr:vnfconfig']['vnf-info']['cust-ip'])
        self.assertEqual('9999:99', j_data['cpwr:vnfconfig']['vnf-info']['ntw-ip'])
        self.assertIsInstance(j_data, dict)


if __name__ == '__main__':
    unittest.main()
