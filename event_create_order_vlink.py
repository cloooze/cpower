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
        pass

    def execute(self):
        create_vlink = get_order_items('createVLink', self.order_json, 1)

        if self.order_status == 'ERR':
            self.logger.info('Could not create VLink. Rollbacking VNFs creation...')

            service_id = create_vlink['service']['id']

            # Getting the ntw_policy_rule list
            self.dbman.get_network_service(service_id)
            l = self.dbman.fetchone()['ntw_policy']
            original_vnf_type_list = list()
            if len(l) > 0:
                original_vnf_type_list = l.split(',')

            # Getting current VNFs
            current_vnf_type_list = self.dbman.query('SELECT vnf_type,vnf_id '
                                                     'FROM vnf '
                                                     'WHERE ntw_service_id = ?', (service_id,)).fetchall()

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
            return 'FAILURE'
        else:
            # Processing post-createVLink (sub by CW)
            service_id = create_vlink['service']['id']
            ex_input = json.loads(create_vlink['customInputParams'][0]['value'])
            policy_rule = ex_input['extensions-input']['network-policy']['policy-rule']
            vlink_id, vlink_name = create_vlink['id'], create_vlink['name']

            # Updating Network Service table
            self.dbman.query('UPDATE network_service '
                             'SET vlink_id = ?, vlink_name = ?, ntw_policy = ?  '
                             'WHERE ntw_service_id = ?', (vlink_id, vlink_name, ','.join(policy_rule), service_id))

            # Gathering information from DB to send back to NSO
            # we need: customer_id, chain-left-ip, chain-right-ip, vnflist made of vnfid,vnfname,mgmt-ip,custip(left),ntwip(right)

            self.logger.info('VLink %s with id %s succesfully created.' % (vlink_name, vlink_id))
            self.logger.info('Policy Rule %s successfully stored into database.' % policy_rule)

            self.dbman.query('SELECT customer_id FROM network_service WHERE ntw_service_id = ?', (service_id,))
            customer_id = self.dbman.fetchone()['customer_id']

            self.dbman.query('SELECT vnf_id, vnf_type, vnf_position FROM vnf WHERE vnf.ntw_service_id=?', (service_id,))
            vnfs = self.dbman.fetchall()
            nso_vnfs = list()

            for vnf in vnfs:
                vnf_id = vnf['vnf_id']
                vnf_name = vnf['vnf_type']
                vnf_position = vnf['vnf_position']

                self.dbman.query('SELECT vm_vnic_name, vm_vnic_ip FROM vm, vmvnic WHERE vm.vnf_id=? AND vm.vm_id = vmvnic.vm_id', (vnf_id,))
                vm_vnics = self.dbman.fetchall()
                for vm_vnic in vm_vnics:
                    if 'left' in vm_vnic['vm_vnic_name']:
                        left_ip = vm_vnic['vm_vnic_ip']
                    elif 'right' in vm_vnic['vm_vnic_name']:
                        right_ip = vm_vnic['vm_vnic_ip']
                    else:
                        mgmt_ip = vm_vnic['vm_vnic_ip']

                nso_vnf = {'operation': 'create', 'vnf-id': vnf_id, 'vnf-name': vnf_name, 'mgmt-ip': mgmt_ip, 'cust-ip': left_ip, 'ntw-ip': right_ip}
                nso_vnfs.append(nso_vnf)

                if vnf_position == 1:
                    chain_left_ip = left_ip
                if vnf_position == len(vnfs):
                    chain_right_ip = right_ip

            nso_util.notify_nso('createService', nso_util.get_create_vnf_data_response('success', customer_id, chain_left_ip, chain_right_ip, nso_vnfs))

