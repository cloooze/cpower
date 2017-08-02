#!/usr/bin/env python

import sqlite3
import ecm_util as ecm_util
import nso_util as nso_util
import config as c
from event import Event
from utils import *
import time

INTERNAL_ERROR = '100'
REQUEST_ERROR = '200'
NETWORK_ERROR = '300'


class CreateOrderVlink(Event):
    def __init__(self, order_status, order_id, source_api, order_json):
        super(CreateOrderVlink, self).__init__()

        self.order_json = order_json
        self.order_status = order_status
        self.order_id = order_id
        self.source_api = source_api

    def notify(self):
        service_id = self.event_params['service_id']

        self.dbman.query('SELECT customer_id, notify_nso FROM network_service WHERE ntw_service_id = ?', (service_id, ))
        customer_id = self.dbman.fetchone()['customer_id']

        if self.order_status == 'ERR':
            nso_util.notify_nso('createService', nso_util.get_create_vnf_data_response('failed', customer_id))
        else:
            self.dbman.query('SELECT * FROM vnf WHERE ntw_service_id = ? AND vnf_operation = ? AND vnf_status = ?', (service_id, 'CREATE', 'COMPLETE'))
            res = self.dbman.fetchall()

            vnf_id_type_list = (vnf['vnf_id'] + '_' + vnf['vnf_type'] for vnf in res)

            chain_left_ip = self.dbman.query(
                'SELECT vmvnic.vm_vnic_ip FROM vmvnic, vnf, vm WHERE vnf.ntw_service_id = ? AND vnf.vnf_id = '
                'vm.vnf_id AND vm.vm_id = vmvnic.VM_ID AND vnf.VNF_POSITION = (SELECT MIN(vnf.VNF_POSITION) FROM '
                'vnf WHERE ntw_service_id = ?) AND vmvnic.VM_VNIC_NAME LIKE ?',
                (service_id, service_id, '%left')).fetchone()['vm_vnic_ip']

            chain_right_ip = self.dbman.query(
                'SELECT vmvnic.vm_vnic_ip FROM vmvnic, vnf, vm WHERE vnf.ntw_service_id = ? AND vnf.vnf_id = '
                'vm.vnf_id AND vm.vm_id = vmvnic.VM_ID AND vnf.VNF_POSITION = (SELECT MAX(vnf.VNF_POSITION) FROM '
                'vnf WHERE ntw_service_id = ?) AND vmvnic.VM_VNIC_NAME LIKE ?',
                (service_id, service_id, '%right')).fetchone()['vm_vnic_ip']

            nso_vnf_list = list()

            for vnf_id_type in vnf_id_type_list:
                res = self.dbman.query('SELECT vm_vnic_name, vm_vnic_ip FROM vm, vmvnic WHERE vm.vnf_id = ? AND vm.vm_id = vmvnic.vm_id', (vnf_id_type.split('_')[0], )).fetchall()
                for v in res:
                    if 'left' in v['vm_vnic_name']:
                        left_ip = v['vm_vnic_ip']
                    elif 'right' in v['vm_vnic_name']:
                        right_ip = v['vm_vnic_ip']
                    elif 'mgmt' in v['vm_vnic_name']:
                        mgmt_ip = v['vm_vnic_ip']

                nso_vnf_list.append(
                    {'operation': 'create',
                     'vnf-id': vnf_id_type.split('_')[0],
                     'vnf-name': vnf_id_type.split('_')[1],
                     'mgmt-ip': mgmt_ip,
                     'left-ip': left_ip,
                     'right-ip': right_ip})

            nso_util.notify_nso('createService', nso_util.get_create_vnf_data_response('success', customer_id, service_id, chain_left_ip, chain_right_ip, nso_vnf_list))

            self.dbman.query('UPDATE vnf SET notify_nso=? WHERE vnf_id IN ?', ('YES', tuple(vnf_id_type.split('-')[0])))
            self.dbman.notify_nso(service_id)

    def execute(self):
        create_vlink = get_order_items('createVLink', self.order_json, 1)
        service_id = create_vlink['service']['id']

        self.event_params = {'service_id': service_id}

        # TODO doble check NSO notification in case of rollback
        if self.order_status == 'ERR':
            return 'FAILURE'
        else:
            # Processing post-createVLink (sub by CW)
            ex_input = json.loads(create_vlink['customInputParams'][0]['value'])
            policy_rule = ex_input['extensions-input']['network-policy']['policy-rule']
            vlink_id, vlink_name = create_vlink['id'], create_vlink['name']

            # Updating Network Service table
            self.dbman.query('UPDATE network_service '
                             'SET vlink_id = ?, vlink_name = ?, ntw_policy = ?  '
                             'WHERE ntw_service_id = ?', (vlink_id, vlink_name, ','.join(policy_rule), service_id))

            self.logger.info('VLink %s with id %s succesfully created.' % (vlink_name, vlink_id))
            self.logger.info('Policy Rule %s successfully stored into database.' % policy_rule)

    def rollback(self):
        if self.order_status == 'COM':
            return

        self.logger.info('Could not create VLink. Rollbacking VNFs creation...')
        # Getting the ntw_policy_rule list
        service_id = self.event_params['service_id']

        self.dbman.get_network_service(service_id)
        l = self.dbman.fetchone()['ntw_policy']
        original_vnf_type_list = list()
        if len(l) > 0:
            original_vnf_type_list = l.split(',')

        # Getting current VNFs
        current_vnf_type_list = self.dbman.query('SELECT vnf_type, vnf_id '
                                                 'FROM vnf '
                                                 'WHERE ntw_service_id = ?', (service_id,)).fetchall()

        # marking the VNF operation as ROLLBACK/PENDING
        self.dbman.query('UPDATE vnf SET vnf_operation = ?, vnf_status WHERE ntw_service_id = ?',
                         ('ROLLBACK', 'PENDING', service_id))

        # Determining VNFs to delete/to keep
        vnf_to_delete = list()
        vnf_to_keep = list()

        for current_vnf_type in current_vnf_type_list:
            if current_vnf_type['vnf_type'] in original_vnf_type_list:
                vnf_to_keep.append(current_vnf_type['vnf_id'])
            else:
                vnf_to_delete.append(current_vnf_type['vnf_id'])

        self.logger.info('Deleting the VNFs: %s' % vnf_to_delete)
        self.logger.info('Dissociating the VNFs from the Service %s first.' % service_id)

        # Dissociating VNFs to delete from Network Service
        modify_service_json = load_json_file('./json/modify_service.json')

        for vnf_id in vnf_to_keep:
            modify_service_json['vapps'].append({'id': vnf_id})

        modify_service_json['customInputParams'].append(get_cop('next_action', 'skip'))

        ecm_util.invoke_ecm_api(service_id, c.ecm_service_api_services, 'PUT', modify_service_json)

        time.sleep(5)

        # Deleting VNFs
        for vnf_id in vnf_to_delete:
            ecm_util.invoke_ecm_api(vnf_id, c.ecm_service_api_vapps, 'DELETE')

        # Retrieving customer_id for NSO notification
        self.dbman.get_network_service(service_id)
        customer_id = self.dbman.fetchone()['customer_id']

        nso_util.notify_nso('createService', nso_util.get_create_vnf_data_response('failed', customer_id))
