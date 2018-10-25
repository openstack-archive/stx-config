#
# Copyright (c) 2018 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

from sysinv.common import constants
from sysinv.common import exception
from sysinv.common import utils as cutils
from sysinv.common.storage_backend_conf import StorageBackendConfig
from sysinv.openstack.common import log as logging

from . import common
from . import openstack

LOG = logging.getLogger(__name__)

# Info used in the Glance Helm chart.
RBD_STORE_USER = 'images'


class GlanceHelm(openstack.OpenstackBaseHelm):
    """Class to encapsulate helm operations for the glance chart"""

    CHART = constants.HELM_CHART_GLANCE
    SUPPORTED_NAMESPACES = [
        common.HELM_NS_OPENSTACK
    ]

    SERVICE_NAME = 'glance'
    AUTH_USERS = ['glance']

    @property
    def docker_repo_source(self):
        return common.DOCKER_SRC_STX

    @property
    def docker_repo_tag(self):
        return common.DOCKER_SRCS[self.docker_repo_source][common.IMG_TAG_KEY]

    def get_namespaces(self):
        return self.SUPPORTED_NAMESPACES

    def get_overrides(self, namespace=None):
        overrides = {
            common.HELM_NS_OPENSTACK: {
                'pod': self._get_pod_overrides(),
                'endpoints': self._get_endpoints_overrides(),
                'storage': self._get_storage_overrides(),
                'conf': self._get_conf_overrides(),
                'images': self._get_images_overrides(),
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
                'glance_api': self.docker_image,
                'glance_db_sync': self.docker_image,
                'glance_registry': self.docker_image,
                'ks_endpoints': heat_image,
                'ks_service': heat_image,
                'ks_user': heat_image,
            }
        }

    def _get_pod_overrides(self):
        return {
            'replicas': {
                'api': 1,
                'registry': 1,
            }
        }

    def _get_endpoints_overrides(self):
        return {
            'identity': {
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
                    self.SERVICE_NAME, self.AUTH_USERS)
            },
        }

    def _get_storage_overrides(self):
        ceph_backend = self._get_primary_ceph_backend()

        if not ceph_backend:
            return 'pvc'

        return constants.GLANCE_BACKEND_RBD  # radosgw| rbd | swift | pvc

    def _get_ceph_overrides(self):
        SERVICE_PORT_MON = 6789
        # Get Ceph monitors.
        ceph_mon_ips = StorageBackendConfig.get_ceph_mon_ip_addresses(
            self.dbapi).values()
        conf_ceph = {
            'admin_keyring': self._get_ceph_password(
                self.SERVICE_NAME, 'admin_keyring'
            ),
            'monitors': [
                cutils._format_ceph_mon_address(ceph_mon_ips[0], SERVICE_PORT_MON),
                cutils._format_ceph_mon_address(ceph_mon_ips[1], SERVICE_PORT_MON),
                cutils._format_ceph_mon_address(ceph_mon_ips[2], SERVICE_PORT_MON),
            ]
        }

        return conf_ceph

    def _get_conf_overrides(self):
        ceph_backend = self._get_primary_ceph_backend()
        if not ceph_backend:
            rbd_store_pool = ""
            rbd_store_user = ""
        else:
            rbd_store_pool = constants.CEPH_POOL_IMAGES_NAME
            rbd_store_user = RBD_STORE_USER

        conf = {
            'glance': {
                'DEFAULT': {
                    'graceful_shutdown': True,
                    'show_image_direct_url': True,
                },
                'glance_store': {
                    'filesystem_store_datadir': constants.GLANCE_IMAGE_PATH,
                    'rbd_store_pool': rbd_store_pool,
                    'rbd_store_user': rbd_store_user,
                }
            }
        }

        if ceph_backend:
            conf['ceph'] = self._get_ceph_overrides()

        return conf

    def _get_primary_ceph_backend(self):
        try:
            backend = self.dbapi.storage_backend_get_by_name(
                constants.SB_DEFAULT_NAMES[constants.SB_TYPE_CEPH])
        except exception.StorageBackendNotFoundByName:
            backend = None
            pass

        return backend
