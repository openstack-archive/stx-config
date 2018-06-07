#
# Copyright (c) 2018 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

from sysinv.common import constants
from sysinv.common import utils

from . import base
from . import interface


class OVSPuppet(base.BasePuppet):
    """Class to encapsulate puppet operations for vswitch configuration"""

    def __init__(self, *args, **kwargs):
        super(OVSPuppet, self).__init__(*args, **kwargs)

    def get_host_config(self, host):
        config = {}
        if (constants.COMPUTE in utils.get_personalities(host) and
                self._vswitch_type() == constants.VSWITCH_TYPE_OVS_DPDK):
            config.update(self._get_cpu_config(host))
            config.update(self._get_memory_config(host))
            config.update(self._get_port_config(host))
            config.update(self._get_virtual_config(host))
            config.update(self._get_neutron_config(host))
        return config

    def _get_port_config(self, host):
        ovs_devices = {}
        ovs_bridges = {}
        ovs_ports = {}
        ovs_addresses = {}

        index = 0
        for iface in sorted(self.context['interfaces'].values(),
                            key=interface.interface_sort_key):
            if interface.is_data_network_type(iface):
                # create a separate bridge for every configured data interface
                brname = 'br-phy%d' % index
                ovs_bridges[brname] = {}

                # save the associated bridge for provider network mapping
                iface['_ovs_bridge'] = brname

                if iface['iftype'] == constants.INTERFACE_TYPE_ETHERNET:
                    port, devices = self._get_ethernet_port(
                        host, iface, brname, index)
                elif iface['iftype'] == constants.INTERFACE_TYPE_AE:
                    port, devices = self._get_bond_port(
                        host, iface, brname, index)
                elif iface['iftype'] == constants.INTERFACE_TYPE_VLAN:
                    port, devices = self._get_vlan_port(
                        host, iface, brname, index)
                else:
                    raise Exception("unsupported interface type: %s" %
                                    iface['iftype'])

                ovs_ports.update({port['name']: port})
                ovs_devices.update({d['pci_addr']: d for d in devices})

                index += 1

                # currently only one provider network is supported per
                # interface, therefore obtain first entry
                providernet = interface.get_interface_providernets(iface)[0]

                # setup tunnel address if assigned provider network is vxlan
                if self._is_vxlan_providernet(providernet):
                    address = interface.get_interface_primary_address(
                        self.context, iface)
                    if address:
                        ovs_addresses[brname] = {
                            'ifname': brname,
                            'address': address['address'],
                            'prefixlen': address['prefix'],
                        }

        return {
            'platform::vswitch::ovs::devices': ovs_devices,
            'platform::vswitch::ovs::bridges': ovs_bridges,
            'platform::vswitch::ovs::ports': ovs_ports,
            'platform::vswitch::ovs::addresses': ovs_addresses,
        }

    def _get_ethernet_device(self, iface):
        port = interface.get_interface_port(self.context, iface)

        pci_addr = self.quoted_str(port.pciaddr)

        return {
            'pci_addr': pci_addr
        }

    def _get_ethernet_interface(self, host, iface, ifname):

        port = interface.get_interface_port(self.context, iface)

        rxq_count = len(self.context["_ovs_cpus"])

        attributes = [
            "options:dpdk-devargs=%s" % str(port.pciaddr),
            "options:n_rxq=%d" % rxq_count,
            "mtu_request=%d" % iface['imtu']
        ]

        # TODO(mpeters): set other_config:pmd-rxq-affinity to pin receive
        # queues to specific PMD cores

        iftype = 'dpdk'

        return {
            'name': ifname,
            'type': iftype,
            'attributes': attributes,
        }

    def _get_ethernet_port(self, host, iface, bridge, index):
        devices = []
        interfaces = []

        ifname = 'eth%d' % index

        devices.append(self._get_ethernet_device(iface))
        interfaces.append(self._get_ethernet_interface(host, iface, ifname))

        port = {
            'name': ifname,
            'bridge': bridge,
            'interfaces': interfaces,
        }

        return port, devices

    def _get_bond_port(self, host, iface, bridge, index):
        devices = []
        interfaces = []
        attributes = []

        ifname = 'bond%d' % index

        # TODO(mpeters): OVS can support balance-tcp if interface txhashpolicy
        # is set to layer3+4 (currently restricted at API for data interfaces)
        ae_mode = iface['aemode']
        if ae_mode in interface.ACTIVE_STANDBY_AE_MODES:
            attributes.append("bond_mode=active-backup")
        if ae_mode in interface.BALANCED_AE_MODES:
            attributes.append("bond_mode=balance-slb")
        elif ae_mode in interface.LACP_AE_MODES:
            attributes.append("lacp=active")
            attributes.append("bond_mode=balance-slb")
            attributes.append("other_config:lacp-time=fast")

        for member, lower_ifname in enumerate(iface['uses']):
            lower_iface = self.context['interfaces'][lower_ifname]
            member_ifname = '%s.%d' % (ifname, member)

            devices.append(self._get_ethernet_device(lower_iface))
            interfaces.append(self._get_ethernet_interface(
                host, lower_iface, member_ifname))

        port = {
            'type': 'bond',
            'name': ifname,
            'bridge': bridge,
            'attributes': attributes,
            'interfaces': interfaces,
        }

        return port, devices

    def _get_vlan_port(self, host, iface, bridge, index):
        devices = []
        interfaces = []

        ifname = 'vlan%d' % iface['vlan_id']
        attributes = [
            "tag=%d" % iface['vlan_id']
        ]

        lower_iface = interface.get_lower_interface(self.context, iface)

        devices.append(self._get_ethernet_device(lower_iface))
        interfaces.append(self._get_ethernet_interface(
            host, lower_iface, ifname))

        port = {
            'name': ifname,
            'bridge': bridge,
            'attributes': attributes,
            'interfaces': interfaces,
        }

        return port, devices

    def _get_cpu_config(self, host):
        platform_cpus = self._get_platform_cpu_list(host)
        vswitch_cpus = self._get_vswitch_cpu_list(host)

        host_cpus = platform_cpus[:1] + vswitch_cpus[:]

        host_core_list = self.quoted_str(
            ','.join([str(c.cpu) for c in host_cpus]))
        pmd_core_list = self.quoted_str(
            ','.join([str(c.cpu) for c in vswitch_cpus]))

        # save the assigned CPUs for port assignment
        self.context["_ovs_cpus"] = [c.cpu for c in vswitch_cpus]

        return {
            'vswitch::dpdk::host_core_list': host_core_list,
            'vswitch::dpdk::pmd_core_list': pmd_core_list,
        }

    def _get_memory_config(self, host):
        vswitch_memory = []

        host_memory = self.dbapi.imemory_get_by_ihost(host.id)
        for memory in host_memory:
            vswitch_size = memory.vswitch_hugepages_size_mib
            vswitch_pages = memory.vswitch_hugepages_nr
            vswitch_memory.append(str(vswitch_size * vswitch_pages))

        dpdk_socket_mem = self.quoted_str(','.join(vswitch_memory))

        return {
            'vswitch::dpdk::socket_mem': dpdk_socket_mem
        }

    def _get_virtual_config(self, host):
        config = {}
        if utils.is_virtual() or utils.is_virtual_compute(host):
            config.update({
                'platform::vswitch::params::iommu_enabled': False,
                'platform::vswitch::params::hugepage_dir': '/mnt/huge-2048kB',

                'openstack::neutron::params::tunnel_csum': True,
            })
        return config

    def _get_neutron_config(self, host):
        local_ip = None
        tunnel_types = set()
        bridge_mappings = []
        for iface in self.context['interfaces'].values():
            if interface.is_data_network_type(iface):
                # obtain the assigned bridge for interface
                brname = iface.get('_ovs_bridge')
                if brname:
                    providernets = interface.get_interface_providernets(iface)
                    for providernet in providernets:
                        if self._is_vxlan_providernet(providernet):
                            address = interface.get_interface_primary_address(
                                self.context, iface)
                            if address:
                                local_ip = address['address']
                            tunnel_types.add(
                                constants.NEUTRON_PROVIDERNET_VXLAN)
                        else:
                            bridge_mappings.append('%s:%s' %
                                                   (providernet, brname))

        return {
            'neutron::agents::ml2::ovs::local_ip': local_ip,
            'neutron::agents::ml2::ovs::tunnel_types': list(tunnel_types),
            'neutron::agents::ml2::ovs::bridge_mappings': bridge_mappings
        }

    def _get_providernet_type(self, name):
        if name in self.context['providernets']:
            return self.context['providernets'][name]['type']

    def _is_vxlan_providernet(self, name):
        providernet_type = self._get_providernet_type(name)
        return bool(providernet_type == constants.NEUTRON_PROVIDERNET_VXLAN)
