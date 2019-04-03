#
# SPDX-License-Identifier: Apache-2.0
#

from sysinv.common import constants
from sysinv.common import exception
from sysinv.openstack.common import log as logging
from sysinv.helm import common
from sysinv.helm import openstack

LOG = logging.getLogger(__name__)


class FmRestApiHelm(openstack.OpenstackBaseHelm):
    """Class to encapsulate helm operations for the fm-rest-api chart"""

    CHART = constants.HELM_CHART_NOVA_API_PROXY

    SERVICE_NAME = 'fm-rest-api'
    AUTH_USERS = ['fm']

    def get_overrides(self, namespace=None):

        overrides = {
            common.HELM_NS_OPENSTACK: {
                'conf': {
                    'fm': {
                        'DEFAULT': {
                            'keystone_authtoken': {
                                'password': self._generate_random_password(length=16)
                            }
                        }
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
