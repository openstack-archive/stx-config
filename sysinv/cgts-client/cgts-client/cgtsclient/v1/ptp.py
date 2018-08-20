#
# Copyright (c) 2013-2018 Wind River Systems, Inc.
#
# The right to copy, distribute, modify, or otherwise make use
# of this software may be licensed only pursuant to the terms
# of an applicable Wind River license agreement.
#

# -*- encoding: utf-8 -*-
#

from cgtsclient.common import base
from cgtsclient import exc


CREATION_ATTRIBUTES = []


class ptp(base.Resource):
    def __repr__(self):
        return "<ptp %s>" % self._info


class ptpManager(base.Manager):
    resource_class = ptp

    @staticmethod
    def _path(id=None):
        return '/v1/ptp/%s' % id if id else '/v1/ptp'

    def list(self):
        return self._list(self._path(), "ptps")

    def get(self, ptp_id):
        try:
            return self._list(self._path(ptp_id))[0]
        except IndexError:
            return None

    def create(self, **kwargs):
        # path = '/v1/ptp'
        new = {}
        for (key, value) in kwargs.items():
            if key in CREATION_ATTRIBUTES:
                new[key] = value
            else:
                raise exc.InvalidAttribute('%s' % key)
        return self._create(self._path(), new)

    def delete(self, ptp_id):
        # path = '/v1/ptp/%s' % ptp_id
        return self._delete(self._path(ptp_id))

    def update(self, ptp_id, patch):
        # path = '/v1/ptp/%s' % ptp_id
        return self._update(self._path(ptp_id), patch)
