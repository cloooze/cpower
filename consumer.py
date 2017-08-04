#!/usr/bin/env python

from stompest.config import StompConfig
from stompest.protocol import StompSpec
from stompest.sync import Stomp
import xml.etree.ElementTree
import os
import json
import sys
import subprocess
import logging

CONFIG = ''
QUEUE = ''
QUEUE_MAPPING = {
    'OrderComplete': 'OrderCompleteCdwfQ',
    'DesignComplete': 'DesignCompleteQ',
    'ActivationComplete': 'ActivationCompleteQ'
}
TENANT = ''
DISPATCH = ''
EXTERNAL_APP_MAPPING = dict()
logger = logging.getLogger('consumer')


def setup_config():
    """Read configuration file and set everything up"""
    global CONFIG
    global QUEUE
    global EXTERNAL_APP_MAPPING
    global TENANT
    global DISPATCH

    try:
        with open('config.json') as f:
            data = json.load(f)
    except IOError:
        logger.info("Configuration file 'config.json' not found.")
        sys.exit(1)

    hostname = data['stomp']['hostname']
    port = data['stomp']['port']
    event = data['dispatch']['event']

    CONFIG = StompConfig('tcp://%s:%s' % (hostname, port))
    QUEUE = QUEUE_MAPPING[event]
    TENANT = data['dispatch']['tenant']
    DISPATCH = data['dispatch']['command']


def set_env_var(frame_body_elements):
    """Sets information from frame_body to environment variables"""
    for k, v in frame_body_elements.items():
        os.environ[k] = v


def get_env_var_name(s):
    """Returns
       s = 'helloTest' -> 'ECM_HELLO_TEST'
       s = everything else -> s
    """
    i = int()
    for c in s:
        if c.isupper():
            i = s.index(c)
    if i == 1:
        return ('ECM_' + s[:i] + '_' + s[i:]).upper()
    else:
        return s


def parse_frame_body(frame_body):
    el_text = lambda x: None if x is None else x.text

    ns = {'notifications': 'http://www.ericsson.com/ecm/notifications/xml/model'}
    e = xml.etree.ElementTree.fromstring(frame_body)

    frame_elements = dict()
    frame_elements.update({'ECM_TENANT_NAME': el_text(e.find('notifications:tenantName', ns))})
    frame_elements.update({'ECM_VERSION': el_text(e.find('notifications:version', ns))})
    frame_elements.update({'ECM_RESPONSE_INDICATOR': el_text(e.find('notifications:responseIndicator', ns))})
    frame_elements.update({'ECM_ORIGINATOR': el_text(e.find('notifications:originator', ns))})
    frame_elements.update({'ECM_CORRELATION_ID': el_text(e.find('notifications:correlationId', ns))})
    frame_elements.update({'ECM_EVENT_TIME_STAMP': el_text(e.find('notifications:eventTimeStamp', ns))})
    frame_elements.update({'ECM_EVENT_TYPE': el_text(e.find('notifications:eventType', ns))})

    for el in e.findall('notifications:eventParams', ns):
        for p in el.findall('notifications:param', ns):
            frame_elements.update({get_env_var_name(p.find('notifications:tag', ns).text): p.find('notifications:value', ns).text})

    return dict((k, v) for k, v in frame_elements.items() if v is not None)


def log_config():
    logger.info('Subscribed to queue %s...' % QUEUE)
    logger.info('Host %s' % CONFIG.uri)
    logger.info('Tenant: %s' % TENANT)


def setup_logger():
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)


def run():
    """Executes the infinite loop that waits to consume  new messages"""
    client = Stomp(CONFIG)
    client.connect()
    client.subscribe(QUEUE, {StompSpec.ACK_HEADER: StompSpec.ACK_CLIENT_INDIVIDUAL})

    while True:
        frame = client.receiveFrame()
        client.ack(frame)
        frame_body_elements = parse_frame_body(frame.body)
        logger.debug(frame_body_elements)
        set_env_var(frame_body_elements)
        logger.info('Invoking external application: %s' % DISPATCH)
        try:
            res = subprocess.call([DISPATCH])
            logger.info('External application returned exit status %s' % res)
        except Exception:
            logger.error('erroraccio winzoz')

    client.disconnect()


def main():
    setup_logger()
    setup_config()
    log_config()
    run()

if __name__ == '__main__':
    main()


