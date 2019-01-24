#
# Copyright (c) 2018 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

import collections
import copy
import os

from sysinv.common import constants
from sysinv.common import exception
from sysinv.common import utils
from sysinv.openstack.common import log as logging
from sysinv.helm import common
from sysinv.helm import openstack

from oslo_serialization import jsonutils

LOG = logging.getLogger(__name__)


SCHEDULER_FILTERS_COMMON = [
    'RetryFilter',
    'ComputeFilter',
    'BaremetalFilter',
    'AvailabilityZoneFilter',
    'AggregateInstanceExtraSpecsFilter',
    'ComputeCapabilitiesFilter',
    'ImagePropertiesFilter',
    'VCpuModelFilter',
    'NUMATopologyFilter',
    'ServerGroupAffinityFilter',
    'ServerGroupAntiAffinityFilter',
    'PciPassthroughFilter',
    'DiskFilter',
]


DEFAULT_NOVA_PCI_ALIAS = [
    {"vendor_id": constants.NOVA_PCI_ALIAS_QAT_PF_VENDOR,
     "product_id": constants.NOVA_PCI_ALIAS_QAT_DH895XCC_PF_DEVICE,
     "name": constants.NOVA_PCI_ALIAS_QAT_DH895XCC_PF_NAME},
    {"vendor_id": constants.NOVA_PCI_ALIAS_QAT_VF_VENDOR,
     "product_id": constants.NOVA_PCI_ALIAS_QAT_DH895XCC_VF_DEVICE,
     "name": constants.NOVA_PCI_ALIAS_QAT_DH895XCC_VF_NAME},
    {"vendor_id": constants.NOVA_PCI_ALIAS_QAT_PF_VENDOR,
     "product_id": constants.NOVA_PCI_ALIAS_QAT_C62X_PF_DEVICE,
     "name": constants.NOVA_PCI_ALIAS_QAT_C62X_PF_NAME},
    {"vendor_id": constants.NOVA_PCI_ALIAS_QAT_VF_VENDOR,
     "product_id": constants.NOVA_PCI_ALIAS_QAT_C62X_VF_DEVICE,
     "name": constants.NOVA_PCI_ALIAS_QAT_C62X_VF_NAME},
    {"class_id": constants.NOVA_PCI_ALIAS_GPU_CLASS,
     "name": constants.NOVA_PCI_ALIAS_GPU_NAME}
]

SERVICE_PARAM_NOVA_PCI_ALIAS = [
                constants.SERVICE_PARAM_NAME_NOVA_PCI_ALIAS_GPU,
                constants.SERVICE_PARAM_NAME_NOVA_PCI_ALIAS_GPU_PF,
                constants.SERVICE_PARAM_NAME_NOVA_PCI_ALIAS_GPU_VF,
                constants.SERVICE_PARAM_NAME_NOVA_PCI_ALIAS_QAT_DH895XCC_PF,
                constants.SERVICE_PARAM_NAME_NOVA_PCI_ALIAS_QAT_DH895XCC_VF,
                constants.SERVICE_PARAM_NAME_NOVA_PCI_ALIAS_QAT_C62X_PF,
                constants.SERVICE_PARAM_NAME_NOVA_PCI_ALIAS_QAT_C62X_VF,
                constants.SERVICE_PARAM_NAME_NOVA_PCI_ALIAS_USER]


class NovaHelm(openstack.OpenstackBaseHelm):
    """Class to encapsulate helm operations for the nova chart"""

    CHART = constants.HELM_CHART_NOVA
    SUPPORTED_NAMESPACES = [
        common.HELM_NS_OPENSTACK
    ]

    SERVICE_NAME = 'nova'
    AUTH_USERS = ['nova', 'placement']
    SERVICE_USERS = ['neutron', 'ironic']

    def get_namespaces(self):
        return self.SUPPORTED_NAMESPACES

    def get_overrides(self, namespace=None):
        scheduler_filters = SCHEDULER_FILTERS_COMMON

        ssh_privatekey, ssh_publickey = \
            self._get_or_generate_ssh_keys(self.SERVICE_NAME, common.HELM_NS_OPENSTACK)
        overrides = {
            common.HELM_NS_OPENSTACK: {
                'pod': {
                    'user': {
                        'nova': {
                            'uid': 0
                        }
                    }
                },
                'manifests': {
                    'cron_job_cell_setup': False,
                    'cron_job_service_cleaner': False
                },
                'conf': {
                    'ceph': {
                        'enabled': False
                    },
                    'nova': {
                        'DEFAULT': {
                            'default_mempages_size': 2048,
                            'reserved_host_memory_mb': 0,
                            'compute_monitors': 'cpu.virt_driver',
                            'running_deleted_instance_poll_interval': 60,
                            'mkisofs_cmd': '/usr/bin/genisoimage',
                            'network_allocate_retries': 2,
                            'force_raw_images': False,
                            'concurrent_disk_operations': 2,
                            # Set number of block device allocate retries and interval
                            # for volume create when VM boots and creates a new volume.
                            # The total block allocate retries time is set to 2 hours
                            # to satisfy the volume allocation time on slow RPM disks
                            # which may take 1 hour and a half per volume when several
                            # volumes are created in parallel.
                            'block_device_allocate_retries_interval': 3,
                            'block_device_allocate_retries': 2400,
                            'disk_allocation_ratio': 1.0,
                            'cpu_allocation_ratio': 16.0,
                            'ram_allocation_ratio': 1.0,
                            'remove_unused_original_minimum_age_seconds': 3600,
                            'enable_new_services': False,
                            'map_new_hosts': False
                        },
                        'libvirt': {
                            'virt_type': self._get_virt_type(),
                            'cpu_mode': 'none',
                            'live_migration_completion_timeout': 180,
                            'live_migration_permit_auto_converge': True,
                            'mem_stats_period_seconds': 0,
                            'rbd_secret_uuid': None,
                            'rbd_user': None,
                            # Allow up to 1 day for resize confirm
                            'remove_unused_resized_minimum_age_seconds': 86400
                        },
                        'database': {
                            'max_overflow': 64,
                            'idle_timeout': 60,
                            'max_pool_size': 1
                        },
                        'api_database': {
                            'max_overflow': 64,
                            'idle_timeout': 60,
                            'max_pool_size': 1
                        },
                        'cell0_database': {
                            'max_overflow': 64,
                            'idle_timeout': 60,
                            'max_pool_size': 1
                        },
                        'placement': {
                            'os_interface': 'internal'
                        },
                        'neutron': {
                            'default_floating_pool': 'public'
                        },
                        'notifications': {
                            'notification_format': 'unversioned'
                        },
                        'filter_scheduler': {
                            'enabled_filters': scheduler_filters,
                            'ram_weight_multiplier': 0.0,
                            'disk_weight_multiplier': 0.0,
                            'io_ops_weight_multiplier': -5.0,
                            'pci_weight_multiplier': 0.0,
                            'soft_affinity_weight_multiplier': 0.0,
                            'soft_anti_affinity_weight_multiplier': 0.0
                        },
                        'scheduler': {
                            'periodic_task_interval': -1,
                            'discover_hosts_in_cells_interval': 30
                        },
                        'metrics': {
                            'required': False,
                            'weight_setting_multi': 'vswitch.multi_avail=100.0',
                            'weight_setting': 'vswitch.max_avail=100.0'
                        },
                        'vnc': {
                            'novncproxy_base_url': self._get_novncproxy_base_url(),
                        },
                        'pci_extended': {
                            'alias': self._get_pci_alias(),
                        },
                        'upgrade_levels': 'None'
                    },
                    'overrides': {
                        'nova_compute': {
                            'hosts': self._get_per_host_overrides()
                        }
                    },
                    'ssh_private': ssh_privatekey,
                    'ssh_public': ssh_publickey,
                },
                'endpoints': self._get_endpoints_overrides(),
                'images': self._get_images_overrides(),
                'network': {
                    'sshd': {
                        'enabled': True,
                        'from_subnet': self._get_ssh_subnet(),
                    }
                }
            }
        }

        if namespace in self.SUPPORTED_NAMESPACES:
            return overrides[namespace]
        elif namespace:
            raise exception.InvalidHelmNamespace(chart=self.CHART,
                                                 namespace=namespace)
        else:
            return overrides

    def _get_images_overrides(self):
        heat_image = self._operator.chart_operators[
            constants.HELM_CHART_HEAT].docker_image
        return {
            'tags': {
                'bootstrap': heat_image,
                'db_drop': heat_image,
                'db_init': heat_image,
                'ks_user': heat_image,
                'ks_service': heat_image,
                'ks_endpoints': heat_image,
                'nova_api': self.docker_image,
                'nova_cell_setup': self.docker_image,
                'nova_cell_setup_init': heat_image,
                'nova_compute': self.docker_image,
                'nova_compute_ironic': self.docker_image,
                'nova_compute_ssh': self.docker_image,
                'nova_conductor': self.docker_image,
                'nova_consoleauth': self.docker_image,
                'nova_db_sync': self.docker_image,
                'nova_novncproxy': self.docker_image,
                'nova_placement': self.docker_image,
                'nova_scheduler': self.docker_image,
                'nova_spiceproxy': self.docker_image,
                'nova_spiceproxy_assets': self.docker_image
            }
        }

    def _get_endpoints_overrides(self):
        overrides = {
            'identity': {
                'name': 'keystone',
                'auth': self._get_endpoints_identity_overrides(
                    self.SERVICE_NAME, self.AUTH_USERS),
            },
            'oslo_cache': {
                'auth': {
                    'memcached_secret_key':
                        self._get_common_password('auth_memcache_key')
                }
            },
            'oslo_messaging': {
                'auth': self._get_endpoints_oslo_messaging_overrides(
                    self.SERVICE_NAME, [self.SERVICE_NAME])
            },
        }

        db_passwords = {'auth': self._get_endpoints_oslo_db_overrides(
            self.SERVICE_NAME, [self.SERVICE_NAME])}
        overrides.update({
            'oslo_db': db_passwords,
            'oslo_db_api': copy.deepcopy(db_passwords),
            'oslo_db_cell0': copy.deepcopy(db_passwords),
        })

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

    def _get_novncproxy_base_url(self):
        oam_addr = self._get_oam_address(),
        url = "http://%s:6080/vnc_auto.html" % oam_addr
        return url

    def _get_virt_type(self):
        if utils.is_virtual():
            return 'qemu'
        else:
            return 'kvm'

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

    def _update_host_cpu_maps(self, host, default_config):
        host_cpus = self._get_host_cpu_list(host, threads=True)
        if host_cpus:
            vm_cpus = self._get_host_cpu_list(
                host, function=constants.APPLICATION_FUNCTION, threads=True)
            vm_cpu_list = [c.cpu for c in vm_cpus]
            vm_cpu_fmt = "\"%s\"" % utils.format_range_set(vm_cpu_list)
            default_config.update({'vcpu_pin_set': vm_cpu_fmt})

            shared_cpus = self._get_host_cpu_list(
                host, function=constants.SHARED_FUNCTION, threads=True)
            shared_cpu_map = {c.numa_node: c.cpu for c in shared_cpus}
            shared_cpu_fmt = "\"%s\"" % ','.join(
                "%r:%r" % (node, cpu) for node, cpu in shared_cpu_map.items())
            default_config.update({'shared_pcpu_map': shared_cpu_fmt})

    def _get_port_interface_id_index(self, host):
        """
        Builds a dictionary of ports indexed by interface id.
        """
        ports = {}
        for port in self.dbapi.ethernet_port_get_by_host(host.id):
            ports[port.interface_id] = port
        return ports

    def _get_interface_name_index(self, host):
        """
        Builds a dictionary of interfaces indexed by interface name.
        """
        interfaces = {}
        for iface in self.dbapi.iinterface_get_by_ihost(host.id):
            interfaces[iface.ifname] = iface
        return interfaces

    def _get_address_interface_name_index(self, host):
        """
        Builds a dictionary of address lists indexed by interface name.
        """
        addresses = collections.defaultdict(list)
        for address in self.dbapi.addresses_get_by_host(host.id):
            addresses[address.ifname].append(address)
        return addresses

    def get_interface_port(self, iface_context, iface):
        """
        Determine the port of the underlying device.
        """
        assert iface['iftype'] == constants.INTERFACE_TYPE_ETHERNET
        return iface_context['ports'][iface['id']]

    def _get_pci_pt_whitelist(self, host, iface_context):
        # Process all configured PCI passthrough interfaces and add them to
        # the list of devices to whitelist
        devices = []
        for iface in iface_context['interfaces'].values():
            if iface['ifclass'] in [constants.INTERFACE_CLASS_PCI_PASSTHROUGH]:
                port = self.get_interface_port(iface_context, iface)
                device = {
                    'address': port['pciaddr'],
                    'physical_network': iface['providernetworks']
                }
                devices.append(device)

        # Process all enabled PCI devices configured for PT and SRIOV and
        # add them to the list of devices to whitelist.
        # Since we are now properly initializing the qat driver and
        # restarting sysinv, we need to add VF devices to the regular
        # whitelist instead of the sriov whitelist
        pci_devices = self.dbapi.pci_device_get_by_host(host.id)
        for pci_device in pci_devices:
            if pci_device.enabled:
                device = {
                    'address': pci_device.pciaddr,
                    'class_id': pci_device.pclass_id
                }
                devices.append(device)

        return jsonutils.dumps(devices)

    def _get_pci_sriov_whitelist(self, host, iface_context):
        # Process all configured SRIOV passthrough interfaces and add them to
        # the list of devices to whitelist
        devices = []
        for iface in iface_context['interfaces'].values():
            if iface['ifclass'] in [constants.INTERFACE_CLASS_PCI_SRIOV]:
                port = self.get_interface_port(iface_context, iface)
                device = {
                    'address': port['pciaddr'],
                    'physical_network': iface['providernetworks'],
                    'sriov_numvfs': iface['sriov_numvfs']
                }
                devices.append(device)

        return jsonutils.dumps(devices) if devices else None

    def _get_pci_alias(self):
        """
        Generate global PCI alias configuration for QAT and GPU devices
        as JSON list of dict, since that format is compatible with helm
        _write_overrides() yaml.dump(). This is an intermediate format
        to pass data through helm.

        Upstream nova does not support specification of multiple PCI aliases
        as a list and requires one-alias-per-line 'alias = {...}', and that is
        not YAML compatible.

        Subsequent JSON unmarshalling and special formatting is performed by
        nova chart.
        """
        service_parameters = self._get_service_parameter_configs(
            constants.SERVICE_TYPE_NOVA)

        alias_config = DEFAULT_NOVA_PCI_ALIAS[:]

        if service_parameters is not None:
            for p in SERVICE_PARAM_NOVA_PCI_ALIAS:
                value = self._service_parameter_lookup_one(
                    service_parameters,
                    constants.SERVICE_PARAM_SECTION_NOVA_PCI_ALIAS,
                    p, None)
                if value is not None:
                    # Replace any references to device_id with product_id
                    # This is to align with the requirements of the
                    # Nova PCI request alias schema.
                    # (sysinv used device_id, nova uses product_id)
                    value = value.replace("device_id", "product_id")

                    aliases = value.rstrip(';').split(';')
                    for alias_str in aliases:
                        alias = dict((str(k), str(v)) for k, v in
                                     (x.split('=') for x in
                                      alias_str.split(',')))
                        alias_config.append(alias)

        return jsonutils.dumps(alias_config) if alias_config else None

    def _update_host_pci(self, host, pci_config):
        """
        Generate per-host PCI passthrough and PCI SR-IOV configuration as
        JSON list of dict for passthrough_whitelist, and JSON list of dict
        for sriov_whitelist, since that format is compatible with helm
        _write_overrides() yaml.dump().

        Sending through two separate whitelists overcomes nova limitations:
        - We need runtime initialization of SR-IOV VFs. Nova does not have
          a specific sriov configuration parameter. We need a mechanism
          to pass through this information.

        Subsequent JSON unmarshalling and merging into a single whitelist,
        and runtime initialization of SR-IOV number of VFs is performed by
        nova init chart.
        """
        # obtain interface information specific to this host
        iface_context = {
            'ports': self._get_port_interface_id_index(host),
            'interfaces': self._get_interface_name_index(host),
            'addresses': self._get_address_interface_name_index(host),
        }

        # per-host PCI passthrough whitelist
        pci_config.update(
            {'passthrough_whitelist':
                 self._get_pci_pt_whitelist(host, iface_context)})

        # per-host PCI SR-IOV whitelist
        pci_config.update(
            {'sriov_whitelist':
                 self._get_pci_sriov_whitelist(host, iface_context)})

    def _update_host_storage(self, host, default_config, libvirt_config):
        pvs = self.dbapi.ipv_get_by_ihost(host.id)

        instance_backing = constants.LVG_NOVA_BACKING_IMAGE
        concurrent_disk_operations = constants.LVG_NOVA_PARAM_DISK_OPS_DEFAULT
        rbd_pool = constants.CEPH_POOL_EPHEMERAL_NAME
        rbd_ceph_conf = os.path.join(constants.CEPH_CONF_PATH,
                                     constants.SB_TYPE_CEPH_CONF_FILENAME)

        nova_lvg_uuid = None
        for pv in pvs:
            if (pv.lvm_vg_name == constants.LVG_NOVA_LOCAL and
                    pv.pv_state != constants.PV_ERR):
                nova_lvg_uuid = pv.ilvg_uuid

        if nova_lvg_uuid:
            lvg = self.dbapi.ilvg_get(nova_lvg_uuid)
            instance_backing = lvg.capabilities.get(
                constants.LVG_NOVA_PARAM_BACKING)
            concurrent_disk_operations = lvg.capabilities.get(
                constants.LVG_NOVA_PARAM_DISK_OPS)

        default_config.update({'concurrent_disk_operations': concurrent_disk_operations})

        # If NOVA is a service on a ceph-external backend, use the ephemeral_pool
        # and ceph_conf file that are stored in that DB entry.
        # If NOVA is not on any ceph-external backend, it must be on the internal
        # ceph backend with default "ephemeral" pool and default "/etc/ceph/ceph.conf"
        # config file
        sb_list = self.dbapi.storage_backend_get_list_by_type(
            backend_type=constants.SB_TYPE_CEPH_EXTERNAL)
        if sb_list:
            for sb in sb_list:
                if constants.SB_SVC_NOVA in sb.services:
                    ceph_ext_obj = self.dbapi.storage_ceph_external_get(sb.id)
                    rbd_pool = sb.capabilities.get('ephemeral_pool')
                    rbd_ceph_conf = \
                        constants.CEPH_CONF_PATH + os.path.basename(ceph_ext_obj.ceph_conf)

        if instance_backing == constants.LVG_NOVA_BACKING_IMAGE:
            libvirt_config.update({'images_type': 'default'})
        elif instance_backing == constants.LVG_NOVA_BACKING_REMOTE:
            libvirt_config.update({'images_type': 'rbd',
                                   'images_rbd_pool': rbd_pool,
                                   'images_rbd_ceph_conf': rbd_ceph_conf})

    def _update_host_addresses(self, host, default_config, vnc_config, libvirt_config):
        interfaces = self.dbapi.iinterface_get_by_ihost(host.id)
        addresses = self.dbapi.addresses_get_by_host(host.id)
        cluster_host_network = self.dbapi.network_get_by_type(
            constants.NETWORK_TYPE_CLUSTER_HOST)
        cluster_host_iface = None
        for iface in interfaces:
            interface_network = {'interface_id': iface.id,
                                 'network_id': cluster_host_network.id}
            try:
                self.dbapi.interface_network_query(interface_network)
                cluster_host_iface = iface
            except exception.InterfaceNetworkNotFoundByHostInterfaceNetwork:
                pass

        if cluster_host_iface is None:
            return
        cluster_host_ip = None
        ip_family = None
        for addr in addresses:
            if addr.interface_uuid == cluster_host_iface.uuid:
                cluster_host_ip = addr.address
                ip_family = addr.family

        default_config.update({'my_ip': cluster_host_ip})
        if ip_family == 4:
            vnc_config.update({'vncserver_listen': '0.0.0.0'})
        elif ip_family == 6:
            vnc_config.update({'vncserver_listen': '::0'})

        libvirt_config.update({'live_migration_inbound_addr': cluster_host_ip})
        vnc_config.update({'vncserver_proxyclient_address': cluster_host_ip})

    def _get_ssh_subnet(self):
        cluster_host_network = self.dbapi.network_get_by_type(
            constants.NETWORK_TYPE_CLUSTER_HOST)
        address_pool = self.dbapi.address_pool_get(cluster_host_network.pool_uuid)
        return '%s/%s' % (str(address_pool.network), str(address_pool.prefix))

    def _update_host_memory(self, host, default_config):
        vswitch_2M_pages = []
        vswitch_1G_pages = []
        vm_4K_pages = []
        # The retrieved information is not necessarily ordered by numa node.
        host_memory = self.dbapi.imemory_get_by_ihost(host.id)
        # This makes it ordered by numa node.
        memory_numa_list = utils.get_numa_index_list(host_memory)
        # Process them in order of numa node.
        for node, memory_list in memory_numa_list.items():
            memory = memory_list[0]
            # first the 4K memory
            vm_hugepages_nr_4K = memory.vm_hugepages_nr_4K if (
                    memory.vm_hugepages_nr_4K is not None) else 0
            vm_4K_pages.append(vm_hugepages_nr_4K)
            # Now the vswitch memory of each hugepage size.
            vswitch_2M_page = 0
            vswitch_1G_page = 0
            if memory.vswitch_hugepages_size_mib == constants.MIB_2M:
                vswitch_2M_page = memory.vswitch_hugepages_nr
            elif memory.vswitch_hugepages_size_mib == constants.MIB_1G:
                vswitch_1G_page = memory.vswitch_hugepages_nr
            vswitch_2M_pages.append(vswitch_2M_page)
            vswitch_1G_pages.append(vswitch_1G_page)
        # Build up the config values.
        vswitch_2M = "\"%s\"" % ','.join([str(i) for i in vswitch_2M_pages])
        vswitch_1G = "\"%s\"" % ','.join([str(i) for i in vswitch_1G_pages])
        vm_4K = "\"%s\"" % ','.join([str(i) for i in vm_4K_pages])
        # Add the new entries to the DEFAULT config section.
        default_config.update({
            'compute_vm_4K_pages': vm_4K,
            'compute_vswitch_2M_pages': vswitch_2M,
            'compute_vswitch_1G_pages': vswitch_1G,
        })

    def _get_per_host_overrides(self):
        host_list = []
        hosts = self.dbapi.ihost_get_list()

        for host in hosts:
            if (host.invprovision == constants.PROVISIONED):
                if constants.WORKER in utils.get_personalities(host):

                    hostname = str(host.hostname)
                    default_config = {}
                    vnc_config = {}
                    libvirt_config = {}
                    pci_config = {}
                    self._update_host_cpu_maps(host, default_config)
                    self._update_host_storage(host, default_config, libvirt_config)
                    self._update_host_addresses(host, default_config, vnc_config,
                                                libvirt_config)
                    self._update_host_memory(host, default_config)
                    self._update_host_pci(host, pci_config)
                    host_nova = {
                        'name': hostname,
                        'conf': {
                            'nova': {
                                'DEFAULT': default_config,
                                'vnc': vnc_config,
                                'libvirt': libvirt_config,
                                'pci_extended': pci_config,
                            }
                        }
                    }
                    host_list.append(host_nova)
        return host_list

    def get_region_name(self):
        return self._get_service_region_name(self.SERVICE_NAME)
