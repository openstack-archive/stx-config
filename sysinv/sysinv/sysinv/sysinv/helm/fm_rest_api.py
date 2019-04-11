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

    CHART = constants.HELM_CHART_FM_REST_API

    SERVICE_NAME = 'fm-rest-api'
    AUTH_USERS = ['fm']

    def get_overrides(self, namespace=None):

        overrides = {
            common.HELM_NS_OPENSTACK: {
                'endpoints': self._get_endpoints_overrides(),
            }
        }

        if namespace in self.SUPPORTED_NAMESPACES:
            return overrides[namespace]
        elif namespace:
            raise exception.InvalidHelmNamespace(chart=self.CHART,
                                                 namespace=namespace)
        else:
            return overrides

    def _get_endpoints_overrides(self):
        fm_service_name = self._operator.chart_operators[
            constants.HELM_CHART_FM_REST_API].SERVICE_NAME

        return {
            'identity': {
                'auth': self._get_endpoints_identity_overrides(
                    fm_service_name, self.AUTH_USERS),
            },
        }
