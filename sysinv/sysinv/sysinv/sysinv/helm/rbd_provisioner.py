#
# Copyright (c) 2018 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

from cephclient import wrapper as ceph
from sysinv.common import constants
from sysinv.common import exception
from sysinv.common.storage_backend_conf import K8RbdProvisioner
from sysinv.openstack.common import log as logging

from . import base
from . import common

LOG = logging.getLogger(__name__)


class RbdProvisionerHelm(base.BaseHelm):
    """Class to encapsulate helm operations for the rbd-provisioner chart"""

    CHART = constants.HELM_CHART_RBD_PROVISIONER
    SUPPORTED_NAMESPACES = [
        common.HELM_NS_KUBE_SYSTEM
    ]

    SERVICE_PORT_MON = 6789

    ceph_api = ceph.CephWrapper(
        endpoint='http://localhost:5001/api/v0.1/')

    def get_namespaces(self):
        return self.SUPPORTED_NAMESPACES

    def get_overrides(self, namespace=None):

        def is_rbd_provisioner_bk(bk):
            if bk.services is None:
                return False

            # Note: No support yet for external ceph. For it to work we need to
            # get the ip addresses of the monitors from external ceph conf file
            # or add them as overrides.
            return (bk.backend == constants.CINDER_BACKEND_CEPH and
                    constants.SB_SVC_RBD_PROVISIONER in bk.services)

        backends = self.dbapi.storage_backend_get_list()
        rbd_provisioner_bks = [bk for bk in backends if is_rbd_provisioner_bk(bk)]

        if not rbd_provisioner_bks:
            return {}  # ceph is not configured

        classdefaults = {
            "monitors": self._get_formatted_ceph_monitor_ips(),
            "adminId": constants.K8S_RBD_PROV_USER_NAME,
            "adminSecretName": constants.K8S_RBD_PROV_ADMIN_SECRET_NAME
        }

        # Get tier info.
        tiers = self.dbapi.storage_tier_get_list()

        ruleset = 0
        classes = []
        for bk in rbd_provisioner_bks:
            # Get the ruleset for the new kube-rbd pool.
            tier = next((t for t in tiers if t.forbackendid == bk.id), None)
            if not tier:
                raise Exception("No tier present for backend %s" % bk.name)

            rule_name = "{0}{1}{2}".format(
                tier.name,
                constants.CEPH_CRUSH_TIER_SUFFIX,
                "-ruleset").replace('-', '_')

            # Get the rule for the tier. If we cannot, use the 0 ruleset.
            response, body = self.ceph_api.osd_crush_rule_dump(
                name=rule_name, body='json')
            if response.ok:
                ruleset = body['output']['ruleset']

            # Check namespaces. We need to know on what namespaces to create
            # the secrets for the kube-rbd pools.
            pool_secrets_namespaces = bk.capabilities.get(
                constants.K8S_RBD_PROV_NAMESPACES)
            if not pool_secrets_namespaces:
                raise Exception("Please specify the rbd_provisioner_namespaces"
                                " for the %s backend." % bk.name)

            cls = {
                    "name": K8RbdProvisioner.get_storage_class_name(bk),
                    "pool": K8RbdProvisioner.get_pool(bk),
                    "pool_secrets_namespaces": pool_secrets_namespaces.encode(
                            'utf8', 'strict'),
                    "replication": int(bk.capabilities.get("replication")),
                    "crush_rule": ruleset,
                    "chunk_size": 8,
                    "userId": K8RbdProvisioner.get_user_id(bk),
                    "userSecretName": K8RbdProvisioner.get_user_secret_name(bk)
                  }
            classes.append(cls)

        # Get all the info for creating the ephemeral pool.
        ephemeral_pools = []
        # Right now the ephemeral pool will only use the primary tier.
        ruleset = 0

        sb_list_ext = self.dbapi.storage_backend_get_list_by_type(
            backend_type=constants.SB_TYPE_CEPH_EXTERNAL)
        sb_list = self.dbapi.storage_backend_get_list_by_type(
            backend_type=constants.SB_TYPE_CEPH)

        if sb_list_ext:
            for sb in sb_list_ext:
                if constants.SB_SVC_NOVA in sb.services:
                    rbd_pool = sb.capabilities.get('ephemeral_pool')
                    ephemeral_pool = {
                        "name": rbd_pool,
                        "replication": int(sb.capabilities.get("replication")),
                        "crush_rule": ruleset,
                        "chunk_size": 8,
                    }
                    ephemeral_pools.append(ephemeral_pool)
        # Treat internal CEPH.
        if sb_list:
            ephemeral_pool = {
                "pool": constants.CEPH_POOL_EPHEMERAL_NAME,
                "replication": int(sb_list[0].capabilities.get("replication")),
                "crush_rule": ruleset,
                "chunk_size": 8,
            }
            ephemeral_pools.append(ephemeral_pool)

        overrides = {
            common.HELM_NS_KUBE_SYSTEM: {
                "classdefaults": classdefaults,
                "classes": classes,
                "ephemeral_pools": ephemeral_pools,
            }
        }

        if namespace in self.SUPPORTED_NAMESPACES:
            return overrides[namespace]
        elif namespace:
            raise exception.InvalidHelmNamespace(chart=self.CHART,
                                                 namespace=namespace)
        else:
            return overrides
