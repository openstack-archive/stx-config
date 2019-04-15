#
# Copyright (c) 2018 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

from sysinv.common import constants
from sysinv.common import exception
from sysinv.common import utils as cutils

from sysinv.helm import common
from sysinv.helm import openstack

from sqlalchemy.orm.exc import NoResultFound

class IronicHelm(openstack.OpenstackBaseHelm):
    """Class to encapsulate helm operations for the ironic chart"""

    CHART = constants.HELM_CHART_IRONIC

    SERVICE_NAME = 'ironic'
    SERVICE_USERS = ['glance']
    AUTH_USERS = ['ironic']
    # TODO: customize IRONIC_KEYWORD by service parameter
    IRONIC_KEYWORD = 'ironic'

    def get_overrides(self, namespace=None):
        overrides = {
            common.HELM_NS_OPENSTACK: {
                'pod': {
                    'replicas': {
                        'api': self._num_controllers(),
                        'conductor': self._num_controllers()
                    }
                },
                'network': self._get_network_overrides(),
                'endpoints': self._get_endpoints_overrides()
            }
        }

        if namespace in self.SUPPORTED_NAMESPACES:
            return overrides[namespace]
        elif namespace:
            raise exception.InvalidHelmNamespace(chart=self.CHART,
                                                 namespace=namespace)
        else:
            return overrides

    def _get_endpoints_overrides(self):
        overrides = {
            'identity': {
                'auth': self._get_endpoints_identity_overrides(
                    self.SERVICE_NAME, self.AUTH_USERS),
            },
            'oslo_cache': {
                'auth': {
                    'memcache_secret_key':
                        self._get_common_password('auth_memcache_key')
                }
            },
            'oslo_db': {
                'auth': self._get_endpoints_oslo_db_overrides(
                    self.SERVICE_NAME, self.AUTH_USERS)
            },
            'oslo_messaging': {
                'auth': self._get_endpoints_oslo_messaging_overrides(
                    self.SERVICE_NAME, self.AUTH_USERS)
            },
        }

        # Service user passwords already exist in other chart overrides
        for user in self.SERVICE_USERS:
            overrides['identity']['auth'].update({
                user: {
                    'region_name': self._region_name(),
                    'password': self._get_or_generate_password(
                        user, common.HELM_NS_OPENSTACK, user)
                }
            })

        return overrides

    def _get_ironic_port(self):
        ironic_port = ''
        if self.dbapi is None:
            return ironic_port
        try:
            interface_list = self.dbapi.iinterface_get_all()
            ifaces = dict((i['ifname'], i) for i in interface_list)
            port_list = self.dbapi.port_get_all()
            ports = dict((p['interface_id'], p) for p in port_list)
            # find the first interface with IRONIC_KEYWORD in its name
            for interface in interface_list:
                if self.IRONIC_KEYWORD in interface.ifname:
                    ifname = interface.ifname
                    ironic_port = str(cutils.get_port_name_by_interface_name(
                        ifname, ifaces, ports))
                    break
        except NoResultFound:
            pass
        return ironic_port

    def _get_ironic_addrpool(self):
        ironic_addrpool = {}
        if self.dbapi is None:
            return ironic_addrpool
        try:
            addrpools = self.dbapi.address_pools_get_all()
            for addrpool in addrpools:
                if self.IRONIC_KEYWORD in addrpool.name:
                    ironic_addrpool['cidr'] = str(addrpool.network) + \
                            '/' + str(addrpool.prefix)
                    ironic_addrpool['gateway'] = str(addrpool.gateway_address)
                    ironic_addrpool['start'] = str(addrpool.ranges[0][0])
                    ironic_addrpool['end'] = str(addrpool.ranges[0][1])
        except NoResultFound:
            pass
        return ironic_addrpool

    def _get_ironic_providernet(self):
        providernet = ''
        if self.dbapi is None:
            return providernet
        try:
            filters = {'network_type': 'flat'}
            flat_networks = self.dbapi.datanetworks_get_all(
                filters=filters)
            # find the first flat datanetwork with IRONIC_KEYWORD in its name
            for network in flat_networks:
                if self.IRONIC_KEYWORD in network['name']:
                    providernet = str(network['name'])
                    break
        except NoResultFound:
            pass
        return providernet

    # retrieve ironic network settings from address pools,
    # ironic ethernet port name from interfaces,
    # and ironic provider network from data networks.
    #
    # TODO: Support different ethernet port name for ironic conductor.
    # Currently the name of ironic port should be the same on each
    # controllers to support HA, otherwise the initialization
    # of ironic-conductor-pxe would be failed. It's a limitation
    # from openstack-helm/ironic that ironic conductors use same
    # configuration file for init.
    def _get_network_overrides(self):
        ironic_addrpool = self._get_ironic_addrpool()
        if 'gateway' in ironic_addrpool:
            gateway = ironic_addrpool['gateway']
        else:
            gateway = ''
        if 'cidr' in ironic_addrpool:
            cidr = ironic_addrpool['cidr']
        else:
            cidr = ''
        if 'start' in ironic_addrpool:
            start = ironic_addrpool['start']
        else:
            start = ''
        if 'end' in ironic_addrpool:
            end = ironic_addrpool['end']
        else:
            end = ''

        overrides = {
            'pxe': {
                'device': self._get_ironic_port(),
                'neutron_provider_network': self._get_ironic_providernet(),
                'neutron_subnet_gateway': gateway,
                'neutron_subnet_cidr': cidr,
                'neutron_subnet_alloc_start': start,
                'neutron_subnet_alloc_end': end
            },
        }

        return overrides
