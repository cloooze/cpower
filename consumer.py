#!/usr/bin/env python

from stompest.config import StompConfig
from stompest.protocol import StompSpec
from stompest.sync import Stomp
import xml.etree.ElementTree
import os
import json

CONFIG = ''
QUEUE = ''
QUEUE_MAPPING = {
    'OrderComplete': 'OrderCompleteCdwfQ',
    'DesignComplete': 'DesignCompleteQ',
    'ActivationComplete': 'ActivationCompleteQ'
}
EXTERNAL_APP_MAPPING = dict()


def setup_config():
    """Read configuration file and set up all the configuration needed"""
    global CONFIG
    global QUEUE
    global EXTERNAL_APP_MAPPING
    CONFIG = StompConfig('tcp://10.42.237.150:61613')
    QUEUE = 'OrderCompleteCdwfQ'
    EXTERNAL_APP_MAPPING = {'OrderComplete': 'app_name'}

    # TODO fetch config from external JSON file
    """
    {
   "stomp": {
      "hostname": "localhost",
      "port": "61613"
   },
   "dispatch": [
        {
         "event": "OrderComplete",
         "tenant": "Cpower-tenant",
         "command": "./execute_cw.sh"
   }
   ]
   }
    """
    """
    with open('config.json') as f:
        data = json.load(f)

    stomp = data['stomp']
    CONFIG = StompConfig('tcp://%s:%s' % (stomp['hostname'], stomp['port']))

    dispatch = data['dispatch']
    """


def set_env_var(frame_body_elements):
    """Sets information from frame_body to environment variables"""
    for k, v in frame_body_elements.items():
        os.environ[k] = v


def get_env_var_name(s):
    """Returns
       s = 'test' -> 'test'
       s = 'helloTest' -> 'ECM_HELLO_TEST'
    """
    l = list()
    for c in s:
        if c.isupper():
            l.append(s.index(c))
    if len(l) == 1:
        return ('ECM_' + s[:l[0]] + '_' + s[l[0]:]).upper()
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


def run():
    """Executes the infinite loop that waits for new messages"""
    client = Stomp(CONFIG)
    client.connect()
    client.subscribe(QUEUE, {StompSpec.ACK_HEADER: StompSpec.ACK_CLIENT_INDIVIDUAL})
    # client.subscribe('DesignCompleteQ', {StompSpec.ACK_HEADER: StompSpec.ACK_CLIENT_INDIVIDUAL})
    while True:
        frame = client.receiveFrame()
        #print('Frame info %s' % frame.info())
        #print('Frame command %s' % frame.command)
        #print('Frame headers %s' % frame.headers)
        #print('Frame body %s' % frame.body)
        client.ack(frame)
        frame_body_elements = parse_frame_body(frame.body)
        print frame_body_elements
        set_env_var(frame_body_elements)

    client.disconnect()


def main():
    setup_config()
    run()

if __name__ == '__main__':
    main()


