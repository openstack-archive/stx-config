#
# Copyright (c) 2018 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

from sysinv.common import constants
from sysinv.common import exception
from sysinv.openstack.common import log as logging
from sysinv.helm import common
from sysinv.helm import base

LOG = logging.getLogger(__name__)


class GarbdHelm(base.BaseHelm):
    """Class to encapsulate helm operations for the galera arbitrator chart"""

    # The service name is used to build the standard docker image location.
    # It is intentionally "mariadb" and not "garbd" as they both use the
    # same docker image.
    SERVICE_NAME = 'mariadb'

    CHART = constants.HELM_CHART_GARBD
    SUPPORTED_NAMESPACES = [
        common.HELM_NS_OPENSTACK
    ]

    def get_namespaces(self):
        return self.SUPPORTED_NAMESPACES

    def get_meta_overrides(self, namespace):

        def _meta_overrides():
            if self._num_controllers() < 2:
                # If there are fewer than 2 controllers we'll use a single
                # mariadb server and so we don't want to run garbd.  This
                # will remove "openstack-garbd" from the charts in the
                # openstack-mariadb chartgroup.
                return {
                    'schema': 'armada/ChartGroup/v1',
                    'metadata': {
                        'schema': 'metadata/Document/v1',
                        'name': 'openstack-mariadb',
                    },
                    'data': {
                        'description': 'Mariadb',
                        'sequenced': True,
                        'chart_group': [
                            'openstack-mariadb',
                        ]
                    }
                }
            else:
                return {}

        overrides = {
            common.HELM_NS_OPENSTACK: _meta_overrides()
        }
        if namespace in self.SUPPORTED_NAMESPACES:
            return overrides[namespace]
        elif namespace:
            raise exception.InvalidHelmNamespace(chart=self.CHART,
                                                 namespace=namespace)
        else:
            return overrides

    def get_overrides(self, namespace=None):
        overrides = {
            common.HELM_NS_OPENSTACK: {
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

        return {
            'tags': {
                'garbd': self.docker_image
            }
        }

