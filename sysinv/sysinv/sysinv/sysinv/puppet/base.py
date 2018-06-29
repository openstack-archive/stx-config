#
# Copyright (c) 2017-2018 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

import collections
import abc
import itertools
import netaddr
import os
import six

from sqlalchemy.orm.exc import NoResultFound
from sysinv.common import constants
from sysinv.common import utils
from sysinv.common import exception

from . import quoted_str


@six.add_metaclass(abc.ABCMeta)
class BasePuppet(object):
    """Base class to encapsulate puppet operations for hiera configuration"""

    CONFIG_WORKDIR = '/tmp/config'
    DEFAULT_REGION_NAME = 'RegionOne'
    DEFAULT_SERVICE_PROJECT_NAME = 'services'
    DEFAULT_KERNEL_OPTIONS = constants.SYSTEM_SECURITY_FEATURE_SPECTRE_MELTDOWN_DEFAULT_OPTS

    SYSTEM_CONTROLLER_SERVICES = [
        'keystone',
        'glance',
        'nova',
        'neutron',
        'cinder',
        'dcorch'
    ]

    def __init__(self, operator):
        self._operator = operator

    @property
    def dbapi(self):
        return self._operator.dbapi

    @property
    def context(self):
        return self._operator.context

    @staticmethod
    def quoted_str(value):
        return quoted_str(value)

    @staticmethod
    def _generate_random_password(length=16):
        suffix = "Ti0*"
        num = (length / 2) - len(suffix) / 2
        return os.urandom(num).encode('hex') + suffix

    def _get_system(self):
        system = self.context.get('_system', None)
        if system is None:
            system = self.dbapi.isystem_get_one()
            self.context['_system'] = system
        return system

    def _sdn_enabled(self):
        if self.dbapi is None:
            return False

        system = self._get_system()
        return system.capabilities.get('sdn_enabled', False)

    def _kubernetes_enabled(self):
        if self.dbapi is None:
            return False

        system = self._get_system()
        return system.capabilities.get('kubernetes_enabled', False)

    def _https_enabled(self):
        if self.dbapi is None:
            return False

        system = self._get_system()
        return system.capabilities.get('https_enabled', False)

    def _region_config(self):
        if self.dbapi is None:
            return False

        system = self._get_system()
        return system.capabilities.get('region_config', False)

    def _vswitch_type(self):
        if self.dbapi is None:
            return False

        system = self._get_system()
        return system.capabilities.get('vswitch_type', None)

    def _distributed_cloud_role(self):
        if self.dbapi is None:
            return None

        system = self._get_system()
        return system.distributed_cloud_role

    def _region_name(self):
        """Returns the local region name of the system"""
        if self.dbapi is None:
            return self.DEFAULT_REGION_NAME

        system = self._get_system()
        return system.region_name

    def _get_service_project_name(self):
        if self.dbapi is None:
            return self.DEFAULT_SERVICE_PROJECT_NAME

        system = self._get_system()
        return system.service_project_name

    def _get_service(self, service_name):
        if self.dbapi is None:
            return None

        try:
            service = self.dbapi.service_get(service_name)
        except exception.ServiceNotFound:
            # service not configured
            return None
        return service

    def _get_shared_services(self):
        if self.dbapi is None:
            return []

        system = self._get_system()
        return system.capabilities.get('shared_services', [])

    def _get_address_by_name(self, name, networktype):
        """
        Retrieve an address entry by name and scoped by network type
        """
        addresses = self.context.setdefault('_address_names', {})
        address_name = utils.format_address_name(name, networktype)
        address = addresses.get(address_name)
        if address is None:
            address = self.dbapi.address_get_by_name(address_name)
            addresses[address_name] = address

        return address

    def _get_management_address(self):
        address = self._get_address_by_name(
            constants.CONTROLLER_HOSTNAME, constants.NETWORK_TYPE_MGMT)
        return address.address

    def _get_pxeboot_address(self):
        address = self._get_address_by_name(
            constants.CONTROLLER_HOSTNAME, constants.NETWORK_TYPE_PXEBOOT)
        return address.address

    def _get_oam_address(self):
        address = self._get_address_by_name(
            constants.CONTROLLER_HOSTNAME, constants.NETWORK_TYPE_OAM)
        return address.address

    def _get_host_cpu_list(self, host, function=None, threads=False):
        """
        Retreive a list of CPUs for the host, filtered by function and thread
        siblings (if supplied)
        """
        cpus = []
        for c in self.dbapi.icpu_get_by_ihost(host.id):
            if c.thread != 0 and not threads:
                continue
            if c.allocated_function == function or not function:
                cpus.append(c)
        return cpus

    def _get_vswitch_cpu_list(self, host):
        cpus = self._get_host_cpu_list(host, constants.VSWITCH_FUNCTION)
        return sorted(cpus, key=lambda c: c.cpu)

    def _get_platform_cpu_list(self, host):
        cpus = self._get_host_cpu_list(host, constants.PLATFORM_FUNCTION)
        return sorted(cpus, key=lambda c: c.cpu)

    def _get_service_parameters(self, service=None):
        service_parameters = []
        if self.dbapi is None:
            return service_parameters
        try:
            service_parameters = self.dbapi.service_parameter_get_all(
                service=service)
        # the service parameter has not been added
        except NoResultFound:
            pass
        return service_parameters

    def _get_security_feature(self):
        if self.dbapi is None:
            return self.DEFAULT_KERNEL_OPTIONS

        system = self._get_system()
        return system.security_feature

    @staticmethod
    def _service_parameter_lookup_one(service_parameters, section, name,
                                      default):
        for param in service_parameters:
            if param['section'] == section and param['name'] == name:
                return param['value']
        return default

    def _format_service_parameter(self, service_parameters, section, group, name):
        parameter = {}
        key = group + name
        value = self._service_parameter_lookup_one(service_parameters, section,
                                                   name, 'undef')
        if value != 'undef':
            parameter[key] = value
        return parameter

    @staticmethod
    def _format_url_address(address):
        """Format the URL address according to RFC 2732"""
        try:
            addr = netaddr.IPAddress(address)
            if addr.version == constants.IPV6_FAMILY:
                return "[%s]" % address
            else:
                return str(address)
        except netaddr.AddrFormatError:
            return address

    @staticmethod
    def _format_range_set(items):
        # Generate a pretty-printed value of ranges, such as 3-6,8-9,12-17
        ranges = []
        for k, iterable in itertools.groupby(enumerate(sorted(items)),
                                             lambda x: x[1] - x[0]):
            rng = list(iterable)
            if len(rng) == 1:
                s = str(rng[0][1])
            else:
                s = "%s-%s" % (rng[0][1], rng[-1][1])
            ranges.append(s)
        return ','.join(ranges)

    def _get_numa_index_list(self, obj):
        """Create map of objects indexed by numa node"""
        obj_lists = collections.defaultdict(list)
        for index, o in enumerate(obj):
            o["_index"] = index
            obj_lists[o.numa_node].append(o)
        return obj_lists
