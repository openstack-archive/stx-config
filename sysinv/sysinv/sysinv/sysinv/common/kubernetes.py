#
# Copyright (c) 2013-2018 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

# vim: tabstop=4 shiftwidth=4 softtabstop=4

# All Rights Reserved.
#

""" System Inventory Kubernetes Utilities and helper functions."""

from __future__ import absolute_import
import json

from kubernetes import config
from kubernetes import client
from kubernetes.client.rest import ApiException
from six.moves import http_client as httplib
from sysinv.common import exception
from sysinv.openstack.common import log as logging

LOG = logging.getLogger(__name__)


class KubeOperator(object):

    def __init__(self, dbapi):
        self._dbapi = dbapi
        self._kube_client = None
        self._configuration = None

    def _get_kubernetesclient(self, token_id):
        if not self._configuration:
            config.load_kube_config('/etc/kubernetes/admin.conf')
            configuration = client.Configuration()
            configuration.verify_ssl = False
            # Add a Bearer Tag to the token for all external kubeApi calls
            configuration.api_key_prefix['authorization'] = 'Bearer'
            self._configuration = configuration

        # Pass a new token with every request
        self._configuration.api_key['authorization'] = token_id

        if not self._kube_client:
            kubeapi_config = client.ApiClient(self._configuration)
            self._kube_client = client.CoreV1Api(kubeapi_config)

        return self._kube_client

    def kube_patch_node(self, context, name, body):
        try:
            api_token = context.auth_token
            api_response = self._get_kubernetesclient(api_token).patch_node(name, body)
            LOG.debug("Response: %s" % api_response)
        except ApiException as e:
            if e.status == httplib.UNPROCESSABLE_ENTITY:
                reason = json.loads(e.body).get('message', "")
                raise exception.HostLabelInvalid(reason=reason)
        except Exception as e:
            LOG.error("Kubernetes exception: %s" % e)
            raise
