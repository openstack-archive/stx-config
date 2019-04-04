# vim: tabstop=4 shiftwidth=4 softtabstop=4
# coding=utf-8

# Copyright 2013 Hewlett-Packard Development Company, L.P.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#
# Copyright (c) 2013-2018 Wind River Systems, Inc.
#

"""
Client side of the conductor RPC API.
"""

from sysinv.objects import base as objects_base
import sysinv.openstack.common.rpc.proxy
from sysinv.openstack.common import log

LOG = log.getLogger(__name__)

MANAGER_TOPIC = 'sysinv.conductor_manager'


class ConductorAPI(sysinv.openstack.common.rpc.proxy.RpcProxy):
    """Client side of the conductor RPC API.

    API version history:

        1.0 - Initial version.
        1.1 - Used for R5
    """

    RPC_API_VERSION = '1.1'

    def __init__(self, topic=None):
        if topic is None:
            topic = MANAGER_TOPIC

        super(ConductorAPI, self).__init__(
            topic=topic,
            serializer=objects_base.SysinvObjectSerializer(),
            default_version='1.0',
            version_cap=self.RPC_API_VERSION)

    def handle_dhcp_lease(self, context, tags, mac, ip_address, cid=None):
        """Synchronously, have a conductor handle a DHCP lease update.

        Handling depends on the interface:
        - management interface: creates an ihost
        - infrastructure interface: just updated the dnsmasq config

        :param context: request context.
        :param tags: specifies the interface type (mgmt or infra)
        :param mac: MAC for the lease
        :param ip_address: IP address for the lease
        :param cid: Client ID for the lease
        """
        return self.call(context,
                         self.make_msg('handle_dhcp_lease',
                                       tags=tags,
                                       mac=mac,
                                       ip_address=ip_address,
                                       cid=cid))

    def create_ihost(self, context, values):
        """Synchronously, have a conductor create an ihost.

        Create an ihost in the database and return an object.

        :param context: request context.
        :param values: dictionary with initial values for new ihost object
        :returns: created ihost object, including all fields.
        """
        return self.call(context,
                         self.make_msg('create_ihost',
                                       values=values))

    def update_ihost(self, context, ihost_obj):
        """Synchronously, have a conductor update the ihosts's information.

        Update the ihost's information in the database and return an object.

        :param context: request context.
        :param ihost_obj: a changed (but not saved) ihost object.
        :returns: updated ihost object, including all fields.
        """
        return self.call(context,
                         self.make_msg('update_ihost',
                                       ihost_obj=ihost_obj))

    def configure_ihost(self, context, host,
                        do_worker_apply=False):
        """Synchronously, have a conductor configure an ihost.

        Does the following tasks:
        - Update puppet hiera configuration files for the ihost.
        - Add (or update) a host entry in the dnsmasq.conf file.
        - Set up PXE configuration to run installer

        :param context: request context.
        :param host: an ihost object.
        :param do_worker_apply: apply the newly created worker manifests.
        """
        return self.call(context,
                         self.make_msg('configure_ihost',
                                       host=host,
                                       do_worker_apply=do_worker_apply))

    # TODO(CephPoolsDecouple): remove
    def configure_osd_pools(self, context, ceph_backend=None, new_pool_size=None, new_pool_min_size=None):
        """Configure or update configuration of the OSD pools.
        If none of the optionals are provided then all pools are updated based on DB configuration.

        :param context: an admin context.
        :param ceph_backend: Optional ceph backend object of a tier
        :param new_pool_size: Optional override for replication number.
        :param new_pool_min_size: Optional override for minimum replication number.
        """
        return self.call(context,
                 self.make_msg('configure_osd_pools',
                               ceph_backend=ceph_backend,
                               new_pool_size=new_pool_size,
                               new_pool_min_size=new_pool_min_size))

    def remove_host_config(self, context, host_uuid):
        """Synchronously, have a conductor remove configuration for a host.

        Does the following tasks:
        - Remove the hiera config files for the host.

        :param context: request context.
        :param host_uuid: uuid of the host.
        """
        return self.call(context,
                         self.make_msg('remove_host_config',
                                       host_uuid=host_uuid))

    def unconfigure_ihost(self, context, ihost_obj):
        """Synchronously, have a conductor unconfigure an ihost.

        Does the following tasks:
        - Remove hiera config files for the ihost.
        - Remove the host entry from the dnsmasq.conf file.
        - Remove the PXE configuration

        :param context: request context.
        :param ihost_obj: an ihost object.
        """
        return self.call(context,
                         self.make_msg('unconfigure_ihost',
                                       ihost_obj=ihost_obj))

    def create_controller_filesystems(self, context, rootfs_device):
        """Synchronously, create the controller file systems.

        Does the following tasks:
        - queries OS for root disk size
        - creates the controller file systems.
        - queries system to get region info for img_conversion_size setup.


        :param context: request context..
        :param rootfs_device: the root disk device
        """
        return self.call(context,
                         self.make_msg('create_controller_filesystems',
                                       rootfs_device=rootfs_device))

    def get_ihost_by_macs(self, context, ihost_macs):
        """Finds ihost db entry based upon the mac list

        This method returns an ihost if it matches a mac

        :param context: an admin context
        :param ihost_macs: list of mac addresses
        :returns: ihost object, including all fields.
        """

        return self.call(context,
                         self.make_msg('get_ihost_by_macs',
                                       ihost_macs=ihost_macs))

    def get_ihost_by_hostname(self, context, ihost_hostname):
        """Finds ihost db entry based upon the ihost hostname

        This method returns an ihost if it matches the
        hostname.

        :param context: an admin context
        :param ihost_hostname: ihost hostname
        :returns: ihost object, including all fields.
        """

        return self.call(context,
                         self.make_msg('get_ihost_by_hostname',
                                       ihost_hostname=ihost_hostname))

    def iport_update_by_ihost(self, context,
                              ihost_uuid, inic_dict_array):
        """Create iports for an ihost with the supplied data.

        This method allows records for iports for ihost to be created.

        :param context: an admin context
        :param ihost_uuid: ihost uuid unique id
        :param inic_dict_array: initial values for iport objects
        :returns: pass or fail
        """

        return self.call(context,
                         self.make_msg('iport_update_by_ihost',
                                       ihost_uuid=ihost_uuid,
                                       inic_dict_array=inic_dict_array))

    def lldp_agent_update_by_host(self, context,
                                  host_uuid, agent_dict_array):
        """Create lldp_agents for an ihost with the supplied data.

        This method allows records for lldp_agents for a host to be created.

        :param context: an admin context
        :param ihost_uuid: ihost uuid unique id
        :param agent_dict_array: initial values for lldp_agent objects
        :returns: pass or fail
        """

        return self.call(context,
                         self.make_msg('lldp_agent_update_by_host',
                                       host_uuid=host_uuid,
                                       agent_dict_array=agent_dict_array))

    def lldp_neighbour_update_by_host(self, context,
                                      host_uuid, neighbour_dict_array):
        """Create lldp_neighbours for an ihost with the supplied data.

        This method allows records for lldp_neighbours for a host to be
        created.

        :param context: an admin context
        :param ihost_uuid: ihost uuid unique id
        :param neighbour_dict_array: initial values for lldp_neighbour objects
        :returns: pass or fail
        """

        return self.call(
            context,
            self.make_msg('lldp_neighbour_update_by_host',
                          host_uuid=host_uuid,
                          neighbour_dict_array=neighbour_dict_array))

    def pci_device_update_by_host(self, context,
                                  host_uuid, pci_device_dict_array):
        """Create pci_devices for an ihost with the supplied data.

        This method allows records for pci_devices for ihost to be created.

        :param context: an admin context
        :param host_uuid: ihost uuid unique id
        :param pci_device_dict_array: initial values for device objects
        :returns: pass or fail
        """
        return self.call(context,
                         self.make_msg('pci_device_update_by_host',
                                       host_uuid=host_uuid,
                                       pci_device_dict_array=pci_device_dict_array))

    def inumas_update_by_ihost(self, context,
                               ihost_uuid, inuma_dict_array):
        """Create inumas for an ihost with the supplied data.

        This method allows records for inumas for ihost to be created.

        :param context: an admin context
        :param ihost_uuid: ihost uuid unique id
        :param inuma_dict_array: initial values for inuma objects
        :returns: pass or fail
        """

        return self.call(context,
                         self.make_msg('inumas_update_by_ihost',
                                       ihost_uuid=ihost_uuid,
                                       inuma_dict_array=inuma_dict_array))

    def icpus_update_by_ihost(self, context,
                              ihost_uuid, icpu_dict_array,
                              force_grub_update,
                              ):
        """Create cpus for an ihost with the supplied data.

        This method allows records for cpus for ihost to be created.

        :param context: an admin context
        :param ihost_uuid: ihost uuid unique id
        :param icpu_dict_array: initial values for cpu objects
        :param force_grub_update: bool value to force grub update
        :returns: pass or fail
        """

        return self.call(context,
                         self.make_msg('icpus_update_by_ihost',
                                       ihost_uuid=ihost_uuid,
                                       icpu_dict_array=icpu_dict_array,
                                       force_grub_update=force_grub_update))

    def imemory_update_by_ihost(self, context,
                                ihost_uuid, imemory_dict_array,
                                force_update=False):
        """Create or update memory for an ihost with the supplied data.

        This method allows records for memory for ihost to be created,
        or updated.

        :param context: an admin context
        :param ihost_uuid: ihost uuid unique id
        :param imemory_dict_array: initial values for memory objects
        :param force_update: force a memory update
        :returns: pass or fail
        """

        return self.call(context,
                         self.make_msg('imemory_update_by_ihost',
                                       ihost_uuid=ihost_uuid,
                                       imemory_dict_array=imemory_dict_array,
                                       force_update=force_update))

    def idisk_update_by_ihost(self, context,
                              ihost_uuid, idisk_dict_array):
        """Create or update disk for an ihost with the supplied data.

        This method allows records for disk for ihost to be created,
        or updated.

        :param context: an admin context
        :param ihost_uuid: ihost uuid unique id
        :param idisk_dict_array: initial values for disk objects
        :returns: pass or fail
        """

        return self.call(context,
                         self.make_msg('idisk_update_by_ihost',
                                       ihost_uuid=ihost_uuid,
                                       idisk_dict_array=idisk_dict_array))

    def ilvg_update_by_ihost(self, context,
                             ihost_uuid, ilvg_dict_array):
        """Create or update local volume group for an ihost with the supplied
        data.

        This method allows records for a local volume group for ihost to be
        created, or updated.

        :param context: an admin context
        :param ihost_uuid: ihost uuid unique id
        :param ilvg_dict_array: initial values for local volume group objects
        :returns: pass or fail
        """

        return self.call(context,
                         self.make_msg('ilvg_update_by_ihost',
                                       ihost_uuid=ihost_uuid,
                                       ilvg_dict_array=ilvg_dict_array))

    def ipv_update_by_ihost(self, context,
                            ihost_uuid, ipv_dict_array):
        """Create or update physical volume for an ihost with the supplied
        data.

        This method allows records for a physical volume for ihost to be
        created, or updated.

        R5 - Moved to version 1.1 as partition schema is no longer applicable
        to R4

        :param context: an admin context
        :param ihost_uuid: ihost uuid unique id
        :param ipv_dict_array: initial values for physical volume objects
        :returns: pass or fail
        """

        return self.call(context,
                         self.make_msg('ipv_update_by_ihost',
                                       ihost_uuid=ihost_uuid,
                                       ipv_dict_array=ipv_dict_array),
                         version='1.1')

    def ipartition_update_by_ihost(self, context,
                                   ihost_uuid, ipart_dict_array):

        """Create or update partitions for an ihost with the supplied data.

        This method allows records for a host's partition to be created or
        updated.

        :param context: an admin context
        :param ihost_uuid: ihost uuid unique id
        :param ipart_dict_array: initial values for partition objects
        :returns: pass or fail
        """

        return self.call(context,
                         self.make_msg('ipartition_update_by_ihost',
                                       ihost_uuid=ihost_uuid,
                                       ipart_dict_array=ipart_dict_array))

    def update_partition_config(self, context, partition):
        """Asynchronously, have a conductor configure the physical volume
        partitions.

        :param context: request context.
        :param partition: dict with partition details.
        """
        LOG.debug("ConductorApi.update_partition_config: sending"
                  " partition to conductor")
        return self.cast(context, self.make_msg('update_partition_config',
                                                partition=partition))

    def iplatform_update_by_ihost(self, context,
                                  ihost_uuid, imsg_dict):
        """Create or update memory for an ihost with the supplied data.

        This method allows records for memory for ihost to be created,
        or updated.

        :param context: an admin context
        :param ihost_uuid: ihost uuid unique id
        :param imsg_dict: inventory message dict
        :returns: pass or fail
        """

        return self.call(context,
                         self.make_msg('iplatform_update_by_ihost',
                                       ihost_uuid=ihost_uuid,
                                       imsg_dict=imsg_dict))

    def upgrade_ihost(self, context, host, load):
        """Synchronously, have a conductor upgrade a host.

        Does the following tasks:
        - Update the pxelinux.cfg file.

        :param context: request context.
        :param host: an ihost object.
        :param load: a load object.
        """
        return self.call(context,
                         self.make_msg('upgrade_ihost_pxe_config', host=host, load=load))

    def configure_isystemname(self, context, systemname):
        """Synchronously, have a conductor configure the system name.

        Does the following tasks:
        - sends a message to conductor
        - who sends a message to all inventory agents
        - who each update their /etc/platform/motd.system

        :param context: request context.
        :param systemname: the systemname
        """
        LOG.debug("ConductorApi.configure_isystemname: sending"
                  " systemname to conductor")
        return self.call(context,
                         self.make_msg('configure_isystemname',
                                       systemname=systemname))

    def configure_system_https(self, context):
        """Synchronously, have a conductor configure the system https/http
        configuration.

        Does the following tasks:
        - sends a message to conductor
        - who sends a message to all inventory agents
        - who each apply the https/http selected  manifests

        :param context: request context.
        """
        LOG.debug("ConductorApi.configure_system_https/http: sending"
                  " configure_system_https to conductor")
        return self.call(context, self.make_msg('configure_system_https'))

    def configure_system_timezone(self, context):
        """Synchronously, have a conductor configure the system timezone.

        Does the following tasks:
        - sends a message to conductor
        - who sends a message to all inventory agents
        - who each apply the timezone manifest

        :param context: request context.
        """
        LOG.debug("ConductorApi.configure_system_timezone: sending"
                  " system_timezone to conductor")
        return self.call(context, self.make_msg('configure_system_timezone'))

    def update_route_config(self, context):
        """Synchronously, have a conductor configure static route.

        Does the following tasks:
        - sends a message to conductor
        - who sends a message to all inventory agents
        - who each apply the route manifest

        :param context: request context.
        """
        LOG.debug("ConductorApi.update_route_config: sending"
                  " update_route_config to conductor")
        return self.call(context, self.make_msg('update_route_config'))

    def update_sriov_config(self, context, host_uuid):
        """Synchronously, have a conductor configure sriov config.

        Does the following tasks:
        - sends a message to conductor
        - who sends a message to all inventory agents
        - who each apply the network manifest

        :param context: request context.
        :param host_uuid: the host unique uuid
        """
        LOG.debug("ConductorApi.update_sriov_config: sending "
                  "update_sriov_config to conductor")
        return self.call(context, self.make_msg('update_sriov_config',
                                                host_uuid=host_uuid))

    def update_distributed_cloud_role(self, context):
        """Synchronously, have a conductor configure the distributed cloud
           role of the system.

        Does the following tasks:
        - sends a message to conductor
        - who sends a message to all inventory agents
        - who each apply the config manifest

        :param context: request context.
        """
        LOG.debug("ConductorApi.update_distributed_cloud_role: sending"
                  " distributed_cloud_role to conductor")
        return self.call(context, self.make_msg('update_distributed_cloud_role'))

    def subfunctions_update_by_ihost(self, context, ihost_uuid, subfunctions):
        """Create or update local volume group for an ihost with the supplied
        data.

        This method allows records for a local volume group for ihost to be
        created, or updated.

        :param context: an admin context
        :param ihost_uuid: ihost uuid unique id
        :param subfunctions: subfunctions of the host
        :returns: pass or fail
        """

        return self.call(context,
                         self.make_msg('subfunctions_update_by_ihost',
                                       ihost_uuid=ihost_uuid,
                                       subfunctions=subfunctions))

    def configure_osd_istor(self, context, istor_obj):
        """Synchronously, have a conductor configure an OSD istor.

        Does the following tasks:
        - Allocates an OSD.
        - Creates or resizes the OSD pools as necessary.

        :param context: request context.
        :param istor_obj: an istor object.
        :returns: istor object, with updated osdid
        """
        return self.call(context,
                         self.make_msg('configure_osd_istor',
                                       istor_obj=istor_obj))

    def unconfigure_osd_istor(self, context, istor_obj):
        """Synchronously, have a conductor unconfigure an istor.

        Does the following tasks:
        - Removes the OSD from the crush map.
        - Deletes the OSD's auth key.
        - Deletes the OSD.

        :param context: request context.
        :param istor_obj: an istor object.
        """
        return self.call(context,
                         self.make_msg('unconfigure_osd_istor',
                                       istor_obj=istor_obj))

    def restore_ceph_config(self, context, after_storage_enabled=False):
        """Restore Ceph configuration during Backup and Restore process.

        :param context: request context.
        :returns: return True if restore is successful or no need to restore
        """
        return self.call(context,
                         self.make_msg('restore_ceph_config',
                                       after_storage_enabled=after_storage_enabled))

    def get_ceph_pool_replication(self, context, ceph_backend=None):
        """Get ceph storage backend pool replication parameters

        :param context: request context.
        :param ceph_backend: ceph backend object type for a tier
        :returns: tuple with (replication, min_replication)
        """
        return self.call(context,
                         self.make_msg('get_ceph_pool_replication',
                                       ceph_backend=ceph_backend))

    def delete_osd_pool(self, context, pool_name):
        """delete an OSD pool

        :param context: request context.
        :param pool_name: the name of the OSD pool
        """
        return self.call(context,
                         self.make_msg('delete_osd_pool',
                                       pool_name=pool_name))

    def list_osd_pools(self, context):
        """list OSD pools

        :param context: request context.
        """
        return self.call(context,
                         self.make_msg('list_osd_pools'))

    def get_osd_pool_quota(self, context, pool_name):
        """Get the quota for an OSD pool

        :param context: request context.
        :param pool_name: the name of the OSD pool
        :returns: dictionary with {"max_objects": num, "max_bytes": num}
        """
        return self.call(context,
                         self.make_msg('get_osd_pool_quota',
                                       pool_name=pool_name))

    def set_osd_pool_quota(self, context, pool, max_bytes=0, max_objects=0):
        """Set the quota for an OSD pool

        :param context: request context.
        :param pool: the name of the OSD pool
        """
        return self.call(context,
                         self.make_msg('set_osd_pool_quota',
                                       pool=pool, max_bytes=max_bytes,
                                       max_objects=max_objects))

    def get_ceph_primary_tier_size(self, context):
        """Get the size of the primary storage tier in the ceph cluster.

        :param context: request context.
        :returns: integer size in GB.
        """
        return self.call(context,
                         self.make_msg('get_ceph_primary_tier_size'))

    def get_ceph_tier_size(self, context, tier_name):
        """Get the size of a storage tier in the ceph cluster.

        :param context: request context.
        :param tier_name: name of the storage tier of interest.
        :returns: integer size in GB.
        """
        return self.call(context,
                         self.make_msg('get_ceph_tier_size',
                                       tier_name=tier_name))

    def get_ceph_cluster_df_stats(self, context):
        """Get the usage information for the ceph cluster.

        :param context: request context.
        """
        return self.call(context,
                         self.make_msg('get_ceph_cluster_df_stats'))

    def get_ceph_pools_df_stats(self, context):
        """Get the usage information for the ceph pools.

        :param context: request context.
        """
        return self.call(context,
                         self.make_msg('get_ceph_pools_df_stats'))

    def get_cinder_lvm_usage(self, context):
        """Get the usage information for the LVM pools.

        :param context: request context.
        """
        return self.call(context,
                         self.make_msg('get_cinder_lvm_usage'))

    def get_cinder_volume_type_names(self, context):
        """Get the names of all currently defined cinder volume types.

        :param context: request context.
        """
        return self.call(context,
                         self.make_msg('get_cinder_volume_type_names'))

    def kill_ceph_storage_monitor(self, context):
        """Stop the ceph storage monitor.
        pmon will not restart it. This should only be used in an
        upgrade/rollback

        :param context: request context.
        """
        return self.call(context,
                         self.make_msg('kill_ceph_storage_monitor'))

    def update_dns_config(self, context):
        """Synchronously, have the conductor update the DNS configuration.

        :param context: request context.
        """
        return self.call(context, self.make_msg('update_dns_config'))

    def update_ntp_config(self, context, service_change=False):
        """Synchronously, have the conductor update the NTP configuration.

        :param context: request context.
        """
        return self.call(context, self.make_msg('update_ntp_config',
                         service_change=service_change))

    def update_ptp_config(self, context):
        """Synchronously, have the conductor update the PTP configuration.

        :param context: request context.
        """
        return self.call(context, self.make_msg('update_ptp_config'))

    def update_system_mode_config(self, context):
        """Synchronously, have the conductor update the system mode
        configuration.

        :param context: request context.
        """
        return self.call(context, self.make_msg('update_system_mode_config'))

    def update_security_feature_config(self, context):
        """Synchronously, have the conductor update the security_feature
        configuration.

        :param context: request context.
        """
        return self.call(context, self.make_msg('update_security_feature_config'))

    def update_oam_config(self, context):
        """Synchronously, have the conductor update the OAM configuration.

        :param context: request context.
        """
        return self.call(context, self.make_msg('update_oam_config'))

    def update_user_config(self, context):
        """Synchronously, have the conductor update the user configuration.

        :param context: request context.
        """
        return self.call(context, self.make_msg('update_user_config'))

    def update_storage_config(self, context, update_storage=False,
                              reinstall_required=False, reboot_required=True,
                              filesystem_list=None):
        """Synchronously, have the conductor update the storage configuration.

        :param context: request context.
        """
        return self.call(
            context, self.make_msg(
                'update_storage_config',
                update_storage=update_storage,
                reinstall_required=reinstall_required,
                reboot_required=reboot_required,
                filesystem_list=filesystem_list
            )
        )

    def update_lvm_config(self, context):
        """Synchronously, have the conductor update the LVM configuration.

        :param context: request context.
        """
        return self.call(context, self.make_msg('update_lvm_config'))

    def update_ceph_base_config(self, context, personalities):
        """Synchronously, have the conductor update the configuration
        for monitors and ceph.conf.

        :param context: request context.
        :param personalities: list of host personalities.
        """
        return self.call(
            context, self.make_msg(
                'update_ceph_base_config',
                personalities=personalities
            )
        )

    def update_ceph_osd_config(self, context, host, stor_uuid, runtime_manifests):
        """Synchronously, have the conductor update the configuration
        for an OSD.

        :param context: request context.
        :param host: a host to update OSDs on.
        :param stor_uuid: uuid of a storage device
        :param runtime_manifests: True if puppet manifests are to be applied at
               runtime.
        """
        return self.call(
            context, self.make_msg(
                'update_ceph_osd_config',
                host=host,
                stor_uuid=stor_uuid,
                runtime_manifests=runtime_manifests
            )
        )

    def update_drbd_config(self, context):
        """Synchronously, have the conductor update the drbd configuration.

        :param context: request context.
        """
        return self.call(context, self.make_msg('update_drbd_config'))

    def update_remotelogging_config(self, context, timeout=None):
        """Synchronously, have the conductor update the remotelogging
        configuration.

        :param context: request context.
        :param ihost_uuid: ihost uuid unique id
        """
        return self.call(context,
                         self.make_msg('update_remotelogging_config'), timeout=timeout)

    def get_magnum_cluster_count(self, context):
        """Synchronously, have the conductor get magnum cluster count
        configuration.

        :param context: request context.
        """
        return self.call(context,
                         self.make_msg('get_magnum_cluster_count'))

    def update_infra_config(self, context):
        """Synchronously, have the conductor update the infrastructure network
        configuration.

        :param context: request context.
        """
        return self.call(context, self.make_msg('update_infra_config'))

    def update_lvm_cinder_config(self, context):
        """Synchronously, have the conductor update Cinder LVM on a controller.

        :param context: request context.
        """
        return self.call(context,
                         self.make_msg('update_lvm_cinder_config'))

    def update_install_uuid(self, context, host_uuid, install_uuid):
        """Synchronously, have an agent update install_uuid on
           a host.

        :param context: request context.
        :parm host_uuid: host uuid to update the install_uuid
        :parm install_uuid: install_uuid
        """
        return self.call(context,
                         self.make_msg('update_install_uuid',
                                       host_uuid=host_uuid,
                                       install_uuid=install_uuid))

    def update_ceph_config(self, context, sb_uuid, services):
        """Synchronously, have the conductor update Ceph on a controller

        :param context: request context
        :param sb_uuid: uuid of the storage backed to apply the ceph config
        :param services: list of services using Ceph.
        """
        return self.call(context,
                         self.make_msg('update_ceph_config',
                                       sb_uuid=sb_uuid,
                                       services=services))

    def update_ceph_external_config(self, context, sb_uuid, services):
        """Synchronously, have the conductor update External Ceph on a controller

        :param context: request context
        :param sb_uuid: uuid of the storage backed to apply the external ceph config
        :param services: list of services using Ceph.
        """
        return self.call(context,
                         self.make_msg('update_ceph_external_config',
                                       sb_uuid=sb_uuid,
                                       services=services))

    def config_update_nova_local_backed_hosts(self, context, instance_backing):
        """Synchronously, have the conductor set the hosts with worker
           functionality and with a certain nova-local instance backing to
           config out-of-date.

           :param context: request context
           :param instance_backing: the host's instance backing
        """
        return self.call(context,
                         self.make_msg('config_update_nova_local_backed_hosts',
                                       instance_backing=instance_backing))

    def update_external_cinder_config(self, context):
        """Synchronously, have the conductor update Cinder Exernal(shared)
           on a controller.

        :param context: request context.
        """
        return self.call(context,
                         self.make_msg('update_external_cinder_config'))

    def get_k8s_namespaces(self, context):
        """Synchronously, get Kubernetes namespaces

        :returns: list of namespacea
        """
        return self.call(context,
                         self.make_msg('get_k8s_namespaces'))

    def report_config_status(self, context, iconfig,
                             status, error=None):
        """ Callback from Sysinv Agent on manifest apply success or failure

        Finalize configuration after manifest apply successfully or perform
        cleanup, log errors and raise alarms in case of failures.

        :param context: request context
        :param iconfig: configuration context
        :param status: operation status
        :param error: serialized exception as a dict of type:
                error = {
                        'class': str(ex.__class__.__name__),
                        'module': str(ex.__class__.__module__),
                        'message': six.text_type(ex),
                        'tb': traceback.format_exception(*ex),
                        'args': ex.args,
                        'kwargs': ex.kwargs
                        }

        The iconfig context is expected to contain a valid REPORT_TOPIC key,
        so that we can correctly identify the set of manifests executed.
        """
        return self.call(context,
                         self.make_msg('report_config_status',
                                       iconfig=iconfig,
                                       status=status,
                                       error=error))

    def update_cpu_config(self, context, host_uuid):
        """Synchronously, have the conductor update the cpu
        configuration.

        :param context: request context.
        :param host_uuid: host unique uuid
        """
        return self.call(context, self.make_msg('update_cpu_config',
                                                host_uuid=host_uuid))

    def iconfig_update_by_ihost(self, context,
                                ihost_uuid, imsg_dict):
        """Create or update iconfig for an ihost with the supplied data.

        This method allows records for iconfig for ihost to be updated.

        :param context: an admin context
        :param ihost_uuid: ihost uuid unique id
        :param imsg_dict: inventory message dict
        :returns: pass or fail
        """

        return self.call(context,
                         self.make_msg('iconfig_update_by_ihost',
                                       ihost_uuid=ihost_uuid,
                                       imsg_dict=imsg_dict))

    def iinterface_get_providernets(self,
                                    context,
                                    pn_names=None):
        """Call neutron to get PN MTUs based on PN names

        This method does not update any records in the db

        :param context: an admin context
        :param pn_names: a list of providenet names
        :returns: pass or fail
        """

        pn_dict = self.call(context,
                            self.make_msg('iinterface_get_providernets',
                                          pn_names=pn_names))

        return pn_dict

    def mgmt_ip_set_by_ihost(self,
                             context,
                             ihost_uuid,
                             mgmt_ip):
        """Call sysinv to update host mgmt_ip (removes previous entry if
           necessary)

        :param context: an admin context
        :param ihost_uuid: ihost uuid
        :param mgmt_ip: mgmt_ip
        :returns: Address
        """

        return self.call(context,
                         self.make_msg('mgmt_ip_set_by_ihost',
                                       ihost_uuid=ihost_uuid,
                                       mgmt_ip=mgmt_ip))

    def infra_ip_set_by_ihost(self,
                              context,
                              ihost_uuid,
                              infra_ip):
        """Call sysinv to update host infra_ip (removes previous entry if
           necessary)

        :param context: an admin context
        :param ihost_uuid: ihost uuid
        :param infra_ip: infra_ip
        :returns: Address
        """

        return self.call(context,
                         self.make_msg('infra_ip_set_by_ihost',
                                       ihost_uuid=ihost_uuid,
                                       infra_ip=infra_ip))

    def neutron_extension_list(self, context):
        """
        Send a request to neutron to query the supported extension list.
        """
        return self.call(context, self.make_msg('neutron_extension_list'))

    def neutron_bind_interface(self, context, host_uuid, interface_uuid,
                               network_type, providernets, mtu,
                               vlans=None, test=False):
        """
        Send a request to neutron to bind an interface to a set of provider
        networks, and inform neutron of some key attributes of the interface
        for semantic checking purposes.
        """
        return self.call(context,
                         self.make_msg('neutron_bind_interface',
                                       host_uuid=host_uuid,
                                       interface_uuid=interface_uuid,
                                       network_type=network_type,
                                       providernets=providernets,
                                       mtu=mtu,
                                       vlans=vlans,
                                       test=test))

    def neutron_unbind_interface(self, context, host_uuid, interface_uuid):
        """
        Send a request to neutron to unbind an interface from a set of
        provider networks.
        """
        return self.call(context,
                         self.make_msg('neutron_unbind_interface',
                                       host_uuid=host_uuid,
                                       interface_uuid=interface_uuid))

    def vim_host_add(self, context, api_token, ihost_uuid,
                     hostname, subfunctions, administrative,
                     operational, availability,
                     subfunction_oper, subfunction_avail, timeout):
        """
        Asynchronously, notify VIM of host add
        """

        return self.cast(context,
                         self.make_msg('vim_host_add',
                                       api_token=api_token,
                                       ihost_uuid=ihost_uuid,
                                       hostname=hostname,
                                       personality=subfunctions,
                                       administrative=administrative,
                                       operational=operational,
                                       availability=availability,
                                       subfunction_oper=subfunction_oper,
                                       subfunction_avail=subfunction_avail,
                                       timeout=timeout))

    def mtc_host_add(self, context, mtc_address, mtc_port, ihost_mtc_dict):
        """
        Asynchronously, notify mtce of host add
        """
        return self.cast(context,
                         self.make_msg('mtc_host_add',
                                       mtc_address=mtc_address,
                                       mtc_port=mtc_port,
                                       ihost_mtc_dict=ihost_mtc_dict))

    def notify_subfunctions_config(self, context,
                                   ihost_uuid, ihost_notify_dict):
        """
        Synchronously, notify sysinv of host subfunctions config status
        """
        return self.call(context,
                         self.make_msg('notify_subfunctions_config',
                                       ihost_uuid=ihost_uuid,
                                       ihost_notify_dict=ihost_notify_dict))

    def ilvg_get_nova_ilvg_by_ihost(self,
                                    context,
                                    ihost_uuid):
        """
        Gets the nova ilvg by ihost.

        returns the nova ilvg if added to the host else returns empty
        list

        """

        ilvgs = self.call(context,
                          self.make_msg('ilvg_get_nova_ilvg_by_ihost',
                                        ihost_uuid=ihost_uuid))

        return ilvgs

    def get_platform_interfaces(self, context, ihost_id):
        """Synchronously, have a agent collect platform interfaces for this
           ihost.

        Gets the mgmt, infra interface names and numa node

        :param context: request context.
        :param ihost_id: id of this host
        :returns: a list of interfaces and their associated numa nodes.
        """
        return self.call(context,
                         self.make_msg('platform_interfaces',
                                       ihost_id=ihost_id))

    def ibm_deprovision_by_ihost(self, context, ihost_uuid, ibm_msg_dict):
        """Update ihost upon notification of board management controller
           deprovisioning.

        This method also allows a dictionary of values to be passed in to
        affort additional controls, if and as needed.

        :param context: an admin context
        :param ihost_uuid: ihost uuid unique id
        :param ibm_msg_dict: values for additional controls or changes
        :returns: pass or fail
        """

        return self.call(context,
                         self.make_msg('ibm_deprovision_by_ihost',
                                       ihost_uuid=ihost_uuid,
                                       ibm_msg_dict=ibm_msg_dict))

    def configure_ttys_dcd(self, context, uuid, ttys_dcd):
        """Synchronously, have a conductor configure the dcd.

        Does the following tasks:
        - sends a message to conductor
        - who sends a message to all inventory agents
        - who has the uuid updates dcd

        :param context: request context.
        :param uuid: the host uuid
        :param ttys_dcd: the flag to enable/disable dcd
        """
        LOG.debug("ConductorApi.configure_ttys_dcd: sending (%s %s) to "
                  "conductor" % (uuid, ttys_dcd))
        return self.call(context,
                         self.make_msg('configure_ttys_dcd',
                                       uuid=uuid, ttys_dcd=ttys_dcd))

    def get_host_ttys_dcd(self, context, ihost_id):
        """Synchronously, have a agent collect carrier detect state for this
           ihost.

        :param context: request context.
        :param ihost_id: id of this host
        :returns: ttys_dcd.
        """
        return self.call(context,
                         self.make_msg('get_host_ttys_dcd',
                                       ihost_id=ihost_id))

    def start_import_load(self, context, path_to_iso, path_to_sig):
        """Synchronously, mount the ISO and validate the load for import

        :param context: request context.
        :param path_to_iso: the file path of the iso on this host
        :param path_to_sig: the file path of the iso's detached signature on
                            this host
        :returns: the newly create load object.
        """
        return self.call(context,
                         self.make_msg('start_import_load',
                                       path_to_iso=path_to_iso,
                                       path_to_sig=path_to_sig))

    def import_load(self, context, path_to_iso, new_load):
        """Asynchronously, import a load and add it to the database

        :param context: request context.
        :param path_to_iso: the file path of the iso on this host
        :param new_load: the load object
        :returns: none.
        """
        return self.cast(context,
                         self.make_msg('import_load',
                                       path_to_iso=path_to_iso,
                                       new_load=new_load))

    def delete_load(self, context, load_id):
        """Asynchronously, cleanup a load from both controllers

        :param context: request context.
        :param load_id: id of load to be deleted
        :returns: none.
        """
        return self.cast(context,
                         self.make_msg('delete_load',
                                       load_id=load_id))

    def finalize_delete_load(self, context):
        """Asynchronously, delete the load from the database

        :param context: request context.
        :returns: none.
        """
        return self.cast(context,
                         self.make_msg('finalize_delete_load'))

    def load_update_by_host(self, context, ihost_id, version):
        """Update the host_upgrade table with the running SW_VERSION

        :param context: request context.
        :param ihost_id: the host id
        :param version: the SW_VERSION from the host
        :returns: none.
        """
        return self.call(context,
                         self.make_msg('load_update_by_host',
                                       ihost_id=ihost_id, sw_version=version))

    def update_service_config(self, context, service=None, do_apply=False):
        """Synchronously, have the conductor update the service parameter.

        :param context: request context.
        :param do_apply: apply the newly created manifests.
        """
        return self.call(context, self.make_msg('update_service_config',
                                                service=service,
                                                do_apply=do_apply))

    def start_upgrade(self, context, upgrade):
        """Asynchronously, have the conductor start the upgrade

        :param context: request context.
        :param upgrade: the upgrade object.
        """
        return self.cast(context, self.make_msg('start_upgrade',
                                                upgrade=upgrade))

    def activate_upgrade(self, context, upgrade):
        """Asynchronously, have the conductor perform the upgrade activation.

        :param context: request context.
        :param upgrade: the upgrade object.
        """
        return self.cast(context, self.make_msg('activate_upgrade',
                                                upgrade=upgrade))

    def complete_upgrade(self, context, upgrade, state):
        """Asynchronously, have the conductor complete the upgrade.

        :param context: request context.
        :param upgrade: the upgrade object.
        :param state: the state of the upgrade before completing
        """
        return self.cast(context, self.make_msg('complete_upgrade',
                                                upgrade=upgrade, state=state))

    def abort_upgrade(self, context, upgrade):
        """Synchronously, have the conductor abort the upgrade.

        :param context: request context.
        :param upgrade: the upgrade object.
        """
        return self.call(context, self.make_msg('abort_upgrade',
                                                upgrade=upgrade))

    def complete_simplex_backup(self, context, success):
        """Asynchronously, complete the simplex upgrade start process

        :param context: request context.
        :param success: If the create_simplex_backup call completed
                """
        return self.cast(context, self.make_msg('complete_simplex_backup',
                                                success=success))

    def get_system_health(self, context, force=False, upgrade=False):
        """
        Performs a system health check.

        :param context: request context.
        :param force: set to true to ignore minor and warning alarms
        :param upgrade: set to true to perform an upgrade health check
        """
        return self.call(context,
                         self.make_msg('get_system_health',
                                       force=force, upgrade=upgrade))

    def reserve_ip_for_first_storage_node(self, context):
        """
        Reserve ip address for the first storage node for Ceph monitor
        when installing Ceph as a second backend

        :param context: request context.
        """
        self.call(context,
                  self.make_msg('reserve_ip_for_first_storage_node'))

    def reserve_ip_for_cinder(self, context):
        """
        Reserve ip address for Cinder's services

        :param context: request context.
        """
        self.call(context,
                  self.make_msg('reserve_ip_for_cinder'))

    def update_sdn_controller_config(self, context):
        """Synchronously, have the conductor update the SDN controller config.

        :param context: request context.
        """
        return self.call(context,
                         self.make_msg('update_sdn_controller_config'))

    def update_sdn_enabled(self, context):
        """Synchronously, have the conductor update the SDN enabled flag

        :param context: request context.
        """
        return self.call(context,
                         self.make_msg('update_sdn_enabled'))

    def update_vswitch_type(self, context):
        """Synchronously, have the conductor update the system vswitch type

        :param context: request context.
        """
        return self.call(context,
                         self.make_msg('update_vswitch_type'))

    def create_barbican_secret(self, context, name, payload):
        """Calls Barbican API to create a secret

        :param context: request context.
        :param name: secret name
        :param payload: secret payload
        """
        return self.call(context,
                         self.make_msg('create_barbican_secret',
                                       name=name,
                                       payload=payload))

    def delete_barbican_secret(self, context, name):
        """Calls Barbican API to delete a secret

        :param context: request context.
        :param name: secret name
        """
        return self.call(context,
                         self.make_msg('delete_barbican_secret',
                                       name=name))

    def update_snmp_config(self, context):
        """Synchronously, have a conductor configure the SNMP configuration.

        Does the following tasks:
        - Update puppet hiera configuration file and apply run time manifest

        :param context: request context.
        """
        return self.call(context,
                         self.make_msg('update_snmp_config'))

    def ceph_manager_config_complete(self, context, applied_config):
        self.call(context,
                  self.make_msg('ceph_service_config_complete',
                                applied_config=applied_config))

    def get_controllerfs_lv_sizes(self, context):
        return self.call(context,
                         self.make_msg('get_controllerfs_lv_sizes'))

    def get_cinder_gib_pv_sizes(self, context):
        return self.call(context,
                         self.make_msg('get_cinder_gib_pv_sizes'))

    def get_cinder_partition_size(self, context):
        return self.call(context,
                         self.make_msg('get_cinder_partition_size'))

    def validate_emc_removal(self, context):
        """
        Check that it is safe to remove the EMC SAN
        """
        return self.call(context, self.make_msg('validate_emc_removal'))

    def validate_hpe3par_removal(self, context, backend):
        """
        Check that it is safe to remove the HPE 3PAR storage array
        """
        return self.call(context,
                         self.make_msg('validate_hpe3par_removal',
                                       backend=backend))

    def validate_hpelefthand_removal(self, context):
        """
        Check that it is safe to remove the HPE Lefthand storage array
        """
        return self.call(context, self.make_msg('validate_hpelefthand_removal'))

    def region_has_ceph_backend(self, context):
        """
        Send a request to primary region to see if ceph backend is configured
        """
        return self.call(context, self.make_msg('region_has_ceph_backend'))

    def get_system_tpmconfig(self, context):
        """
        Retrieve the system tpmconfig object
        """
        return self.call(context, self.make_msg('get_system_tpmconfig'))

    def get_tpmdevice_by_host(self, context, host_id):
        """
        Retrieve the tpmdevice object for this host
        """
        return self.call(context,
                         self.make_msg('get_tpmdevice_by_host',
                                       host_id=host_id))

    def update_tpm_config(self, context, tpm_context):
        """Synchronously, have the conductor update the TPM config.

        :param context: request context.
        :param tpm_context: TPM object context
        """
        return self.call(context,
                         self.make_msg('update_tpm_config',
                                       tpm_context=tpm_context))

    def update_tpm_config_manifests(self, context, delete_tpm_file=None):
        """Synchronously, have the conductor update the TPM config manifests.

        :param context: request context.
        :param delete_tpm_file: tpm file to delete, optional
        """
        return self.call(context,
                         self.make_msg('update_tpm_config_manifests',
                                       delete_tpm_file=delete_tpm_file))

    def tpm_config_update_by_host(self, context,
                                  host_uuid, response_dict):
        """Get TPM configuration status from Agent host.

        This method allows for alarms to be raised for hosts if TPM
        is not configured properly.

        :param context: an admin context
        :param host_uuid: host unique id
        :param response_dict: configuration status
        :returns: pass or fail
        """
        return self.call(
            context,
            self.make_msg('tpm_config_update_by_host',
                          host_uuid=host_uuid,
                          response_dict=response_dict))

    def tpm_device_update_by_host(self, context,
                                  host_uuid, tpmdevice_dict):
        """Synchronously , have the conductor create or update
        a tpmdevice per host.

        :param context: request context.
        :param host_uuid: uuid or id of the host
        :param tpmdevice_dict: a dictionary of tpm device attributes

        :returns: tpmdevice object
        """
        return self.call(
            context,
            self.make_msg('tpm_device_update_by_host',
                          host_uuid=host_uuid,
                          tpmdevice_dict=tpmdevice_dict))

    def cinder_prepare_db_for_volume_restore(self, context):
        """
        Send a request to cinder to remove all volume snapshots and set all
        volumes to error state in preparation for restoring all volumes.

        This is needed for cinder disk replacement.
        """
        return self.call(context,
                         self.make_msg('cinder_prepare_db_for_volume_restore'))

    def cinder_has_external_backend(self, context):
        """
        Check if cinder has loosely coupled external backends.
        These are the possible backends: emc_vnx, hpe3par, hpelefthand

        :param context: request context.
        """
        return self.call(context,
                         self.make_msg('cinder_has_external_backend'))

    def get_ceph_object_pool_name(self, context):
        """
        Get Rados Gateway object data pool name

        :param context: request context.
        """
        return self.call(context,
                         self.make_msg('get_ceph_object_pool_name'))

    def get_software_upgrade_status(self, context):
        """
        Software upgrade status is needed by ceph-manager to take ceph specific
        upgrade actions

        This rpcapi function is added to signal that conductor's
        get_software_upgrade_status function is used by an RPC client

        ceph-manager however doesn't call rpcapi.get_software_upgrade_status and
        instead it uses oslo_messaging to construct a call on conductor's topic
        for this function. The reason is that sysinv is using an old version of
        openstack common and messaging libraries incompatible with the one used
        by ceph-manager.
        """
        return self.call(context,
                         self.make_msg('get_software_upgrade_status'))

    def update_firewall_config(self, context, ip_version, contents):
        """Synchronously, have the conductor update the firewall config
        and manifest.

        :param context: request context.
        :param ip_version: IP version.
        :param contents: file content of custom firewall rules.

        """
        return self.call(context,
                         self.make_msg('update_firewall_config',
                                       ip_version=ip_version,
                                       contents=contents))

    def distribute_ceph_external_config(self, context, ceph_conf_filename):
        """Synchronously, have the conductor update the Ceph configuration
        file for external cluster.

        :param context: request context.
        :param ceph_conf_filename: Ceph conf file

        """
        return self.call(context,
                         self.make_msg('distribute_ceph_external_config',
                                       ceph_conf_filename=ceph_conf_filename))

    def store_ceph_external_config(self, context, contents, ceph_conf_filename):
        """Synchronously, have the conductor to write the ceph config file content
        to /opt/platform/config

        :param context: request context.
        :param contents: file content of the Ceph conf file
        :param ceph_conf_filename: Ceph conf file

        """
        return self.call(context,
                         self.make_msg('store_ceph_external_config',
                                       contents=contents,
                                       ceph_conf_filename=ceph_conf_filename))

    def update_partition_information(self, context, partition_data):
        """Synchronously, have the conductor update partition information.

        :param context: request context.
        :param host_uuid: host UUID
        :param partition_uuid: partition UUID
        :param info: dict containing partition information to update

        """
        return self.call(context,
                         self.make_msg('update_partition_information',
                                       partition_data=partition_data))

    def install_license_file(self, context, contents):
        """Sychronously, have the conductor install the license file.

        :param context: request context.
        :param contents: content of license file.
        """
        return self.call(context,
                         self.make_msg('install_license_file',
                                       contents=contents))

    def config_certificate(self, context, pem_contents, config_dict):
        """Synchronously, have the conductor configure the certificate.

        :param context: request context.
        :param pem_contents: contents of certificate in pem format.
        :param config_dict: dictionary of certificate config attributes.

        """
        return self.call(context,
                         self.make_msg('config_certificate',
                                       pem_contents=pem_contents,
                                       config_dict=config_dict,
                                       ))

    def get_helm_chart_namespaces(self, context, chart_name):
        """Get supported chart namespaces.

        This method retrieves the namespace supported by a given chart.

        :param context: request context.
        :param chart_name: name of the chart
        :returns: list of supported namespaces that associated overrides may be
                  provided.
        """
        return self.call(context,
                         self.make_msg('get_helm_chart_namespaces',
                                       chart_name=chart_name))

    def get_helm_chart_overrides(self, context, chart_name, cnamespace=None):
        """Get the overrides for a supported chart.

        :param context: request context.
        :param chart_name: name of a supported chart
        :param cnamespace: (optional) namespace
        :returns: dict of overrides.

        """
        return self.call(context,
                         self.make_msg('get_helm_chart_overrides',
                                       chart_name=chart_name,
                                       cnamespace=cnamespace))

    def get_helm_application_namespaces(self, context, app_name):
        """Get supported application namespaces.

        :param app_name: name of the bundle of charts required to support an
                         application
        :returns: dict of charts and supported namespaces that associated
                  overrides may be provided.
        """
        return self.call(context,
                         self.make_msg('get_helm_application_namespaces',
                                       app_name=app_name))

    def get_helm_application_overrides(self, context, app_name, cnamespace=None):
        """Get the overrides for a supported set of charts.

        :param context: request context.
        :param app_name: name of a supported application (set of charts)
        :param cnamespace: (optional) namespace
        :returns: dict of overrides.

        """
        return self.call(context,
                         self.make_msg('get_helm_application_overrides',
                                       app_name=app_name,
                                       cnamespace=cnamespace))

    def merge_overrides(self, context, file_overrides=[], set_overrides=[]):
        """Merge the file and set overrides into a single chart overrides.

        :param context: request context.
        :param file_overrides: (optional) list of overrides from files
        :param set_overrides: (optional) list of parameter overrides
        :returns: merged overrides string

        """
        return self.call(context,
                         self.make_msg('merge_overrides',
                                       file_overrides=file_overrides,
                                       set_overrides=set_overrides))

    def update_kubernetes_label(self, context, host_uuid, label_dict):
        """Synchronously, have the conductor update kubernetes label.

        :param context: request context.
        :param host_uuid: uuid or id of the host
        :param label_dict: a dictionary of kubernetes labels
        """
        return self.call(context,
                         self.make_msg('update_kubernetes_label',
                                       host_uuid=host_uuid,
                                       label_dict=label_dict))

    def update_host_memory(self, context, host_uuid):
        """Asynchronously, have a conductor update the host memory

        :param context: request context.
        :param host_uuid: duuid or id of the host.
        """
        LOG.info("ConductorApi.update_host_memory: sending"
                 " host memory update request to conductor")
        return self.cast(context, self.make_msg('update_host_memory',
                                                host_uuid=host_uuid))

    def update_fernet_keys(self, context, keys):
        """Synchronously, have the conductor update fernet keys.

        :param context: request context.
        :param keys: a list of fernet keys
        """
        return self.call(context, self.make_msg('update_fernet_keys',
                                                keys=keys))

    def get_fernet_keys(self, context, key_id=None):
        """Synchronously, have the conductor to retrieve fernet keys.

        :param context: request context.
        :param key_id: (optional)
        :returns: a list of fernet keys.
        """
        return self.call(context, self.make_msg('get_fernet_keys',
                                                key_id=key_id))

    def perform_app_upload(self, context, rpc_app, tarfile):
        """Handle application upload request

        :param context: request context.
        :param rpc_app: data object provided in the rpc request
        :param tafile: location of application tarfile to be extracted
        """
        return self.cast(context,
                         self.make_msg('perform_app_upload',
                                       rpc_app=rpc_app,
                                       tarfile=tarfile))

    def perform_app_apply(self, context, rpc_app):
        """Handle application apply request

        :param context: request context.
        :param rpc_app: data object provided in the rpc request
        """
        return self.cast(context,
                         self.make_msg('perform_app_apply',
                                       rpc_app=rpc_app))

    def perform_app_remove(self, context, rpc_app):
        """Handle application remove request

        :param context: request context.
        :param rpc_app: data object provided in the rpc request

        """
        return self.cast(context,
                         self.make_msg('perform_app_remove',
                                       rpc_app=rpc_app))

    def perform_app_delete(self, context, rpc_app):
        """Handle application delete request

        :param context: request context.
        :param rpc_app: data object provided in the rpc request

        """
        return self.call(context,
                         self.make_msg('perform_app_delete',
                                       rpc_app=rpc_app))
