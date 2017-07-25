#!/usr/bin/env python

from db_manager import DBManager
import logging.config


class Event(object):

    def __init__(self):
        self.dbman = DBManager('cpower.db')
        self.logger = logging.getLogger('cpower')
        self.event_params = {}

    def execute(self):
        raise NotImplementedError()

    def notify(self):
        raise NotImplementedError()

