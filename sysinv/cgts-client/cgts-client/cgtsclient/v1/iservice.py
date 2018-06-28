# -*- encoding: utf-8 -*-
#
# Copyright © 2013 Red Hat, Inc
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#
# Copyright (c) 2013-2014 Wind River Systems, Inc.
#


from cgtsclient.common import base
from cgtsclient import exc


CREATION_ATTRIBUTES = ['servicename', 'hostname', 'state', 'activity', 'reason']
# missing forihostid


class iService(base.Resource):
    def __repr__(self):
        return "<iService %s>" % self._info


class iServiceManager(base.Manager):
    resource_class = iService

    @staticmethod
    def _path(id=None):
        return '/v1/iservice/%s' % id if id else '/v1/iservice'

    def list(self):
        return self._list(self._path(), "iservice")

    def get(self, iservice_id):
        try:
            return self._list(self._path(iservice_id))[0]
        except IndexError:
            return None

    def create(self, **kwargs):
        new = {}
        for (key, value) in kwargs.items():
            if key in CREATION_ATTRIBUTES:
                new[key] = value
            else:
                raise exc.InvalidAttribute()
        return self._create(self._path(), new)

    def delete(self, iservice_id):
        return self._delete(self._path(iservice_id))

    def update(self, iservice_id, patch):
        return self._update(self._path(iservice_id), patch)
