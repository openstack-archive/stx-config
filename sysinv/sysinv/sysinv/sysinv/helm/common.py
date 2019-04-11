#
# Copyright (c) 2018 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

""" System Inventory Helm common top level code."""


import os

from sysinv.openstack.common import log as logging
from tsconfig import tsconfig


LOG = logging.getLogger(__name__)

HELM_OVERRIDES_PATH = os.path.join(tsconfig.PLATFORM_PATH, 'helm', tsconfig.SW_VERSION)

# Namespaces
HELM_NS_CEPH = 'ceph'
HELM_NS_DEFAULT = 'default'
HELM_NS_KUBE_SYSTEM = 'kube-system'
HELM_NS_NFS = 'nfs'
HELM_NS_OPENSTACK = 'openstack'
HELM_NS_HELM_TOOLKIT = 'helm-toolkit'

# Services
# Matches configassistant.py value => Should change to STARLINGX
SERVICE_ADMIN = 'CGCS'

# Users
USER_ADMIN = 'admin'
USER_TEST = 'test'
USERS = [USER_ADMIN, USER_TEST]

# Passwords Formatting
PASSWORD_FORMAT_IDENTITY = 'keystone-auth'
PASSWORD_FORMAT_CEPH = 'ceph-auth'

# Node Labels
LABEL_CONTROLLER = 'openstack-control-plane'
LABEL_COMPUTE_LABEL = 'openstack-compute-node'
LABEL_OPENVSWITCH = 'openvswitch'
LABEL_REMOTE_STORAGE = 'remote-storage'

# Label values
LABEL_VALUE_ENABLED = 'enabled'
LABEL_VALUE_DISABLED = 'disabled'

DEFAULT_UEFI_LOADER_PATH = {
    "x86_64": "/usr/share/OVMF",
    "aarch64": "/usr/share/AAVMF"
}


def get_mount_uefi_overrides():
    uefi_config = {
        'volumes': [
            {
                'name': 'ovmf',
                'hostPath': {
                    'path': DEFAULT_UEFI_LOADER_PATH['x86_64']
                }
            },
            {
                'name': 'aavmf',
                'hostPath': {
                    'path': DEFAULT_UEFI_LOADER_PATH['aarch64']
                }
            }
        ],
        'volumeMounts': [
            {
                'name': 'ovmf',
                'mountPath': DEFAULT_UEFI_LOADER_PATH['x86_64']
            },
            {
                'name': 'aavmf',
                'mountPath': DEFAULT_UEFI_LOADER_PATH['aarch64']
            }
        ]
    }
    return uefi_config
