#!/usr/bin/env python 

import unittest
import ecm_util as ECMUtil
import config as c
from ecm_exception import *


class ECMUtilTest(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_get_ecm_api_auth(self):
        h = ECMUtil.get_ecm_api_auth()
        self.assertEqual('nsotenant', h['TenantId'])

    def test_get_order(self):
        with self.assertRaises(ECMConnectionError):
            ECMUtil.invoke_ecm_api('1112344', c.ecm_service_api_orders, 'GET')

if __name__ == '__main__':
    unittest.main()
