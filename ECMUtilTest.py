#!/usr/bin/env python 

import unittest
import ECMUtil as ECMUtil
import config as c
from ECMException import *


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
            ECMUtil.get_order('1112344')

if __name__ == '__main__':
    unittest.main()
