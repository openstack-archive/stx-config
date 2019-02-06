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


class IngressHelm(base.BaseHelm):
    """Class to encapsulate helm operations for the ingress chart"""

    CHART = constants.HELM_CHART_INGRESS

    # This chart supports more than the default of just openstack.
    SUPPORTED_NAMESPACES = [
        common.HELM_NS_KUBE_SYSTEM,
        common.HELM_NS_OPENSTACK
    ]

    def get_overrides(self, namespace=None):
        # Currently have conflicts with ports 80 and 8080, use 8081 for now
        overrides = {
            common.HELM_NS_KUBE_SYSTEM: {
                'pod': {
                    'replicas': {
                        'error_page': self._num_controllers()
                    }
                },
                'deployment': {
                    'mode': 'cluster',
                    'type': 'DaemonSet'
                },
                'network': {
                    'host_namespace': 'true'
                },
                'endpoints': {
                    'ingress': {
                        'port': {
                            'http': {
                                'default': 8081
                            }
                        }
                    }
                }
            },
            common.HELM_NS_OPENSTACK: {
                'pod': {
                    'replicas': {
                        'ingress': self._num_controllers(),
                        'error_page': self._num_controllers()
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
