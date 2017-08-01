#!/usr/bin/env python

import ecm_util as ecm_util
import nso_util as nso_util
import config as c
from ecm_exception import *
from event import Event
from utils import *
import time


class ModifyVlink(Event):

    def __init__(self, order_status, order_id, source_api, order_json):
        super(ModifyVlink, self).__init__()

        self.order_json = order_json
        self.order_status = order_status
        self.order_id = order_id
        self.source_api = source_api

    def notify(self):
        raise NotImplementedError

    def execute(self):
        raise NotImplementedError

    def rollback(self):
        raise NotImplementedError




