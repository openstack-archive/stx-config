#
# Copyright (c) 2018 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

from sysinv.common import constants
from sysinv.common import exception
from sysinv.common import utils
from sysinv.openstack.common import log as logging
from sysinv.helm import common
from sysinv.helm import openstack

LOG = logging.getLogger(__name__)


class LibvirtHelm(openstack.OpenstackBaseHelm):
    """Class to encapsulate helm operations for the libvirt chart"""

    CHART = constants.HELM_CHART_LIBVIRT

    SERVICE_NAME = 'libvirt'

    def get_overrides(self, namespace=None):
        overrides = {
            common.HELM_NS_OPENSTACK: {
                'conf': {
                    'libvirt': {
                        'listen_addr': '0.0.0.0'
                    },
                    'ceph': {
                        'enabled': False
                    },
                    'qemu': {
                        'user': "root",
                        'group': "root",
                        'cgroup_controllers': ["cpu", "cpuacct"],
                        'namespaces': [],
                        'clear_emulator_capabilities': 0
                    }
                }
            }
        }

        self._get_images_overrides(overrides[common.HELM_NS_OPENSTACK])
        self.update_dependency_options(overrides[common.HELM_NS_OPENSTACK])

        if namespace in self.SUPPORTED_NAMESPACES:
            return overrides[namespace]
        elif namespace:
            raise exception.InvalidHelmNamespace(chart=self.CHART,
                                                 namespace=namespace)
        else:
            return overrides

    def _get_images_overrides(self, overrides_dict):
        if self.docker_repo_source != common.DOCKER_SRC_OSH:
            overrides_dict.update({
                'images': {
                    'tags': {
                        'libvirt': self.docker_image
                    }
                }
            })

    def update_dependency_options(self, overrides):
        if utils.get_vswitch_type(self.dbapi) != 'none':
            overrides.update({
                'dependencies': {
                    'dynamic': {
                        'targeted': {
                            'openvswitch': {
                                'libvirt': None
                            }
                        }
                    }
                }
            })
