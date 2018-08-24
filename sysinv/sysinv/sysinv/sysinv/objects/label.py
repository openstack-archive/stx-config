#
# Copyright (c) 2018 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

# vim: tabstop=4 shiftwidth=4 softtabstop=4
# coding=utf-8
#

from sysinv.db import api as db_api
from sysinv.objects import base
from sysinv.objects import utils


class Label(base.SysinvObject):

    dbapi = db_api.get_instance()

    fields = {
        'uuid': utils.str_or_none,
        'label': utils.str_or_none,
        'host_id': utils.int_or_none,
        'host_uuid': utils.str_or_none,
    }

    _foreign_fields = {'host_uuid': 'host:uuid'}

    @base.remotable_classmethod
    def get_by_uuid(cls, context, uuid):
        return cls.dbapi.label_get(uuid)

    @base.remotable_classmethod
    def get_by_host_id(cls, context, host_id):
        return cls.dbapi.label_get_by_host(host_id)

    def save_changes(self, context, updates):
        self.dbapi.label_update(self.uuid, updates)
