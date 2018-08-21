# vim: tabstop=4 shiftwidth=4 softtabstop=4
# coding: utf-8
#
# Copyright 2013 Red Hat, Inc.
# All Rights Reserved.
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
# Copyright (c) 2013-2015 Wind River Systems, Inc.
#

from oslo_utils import strutils
import re
import six

import wsme
from wsme import types as wtypes

from sysinv.common import exception
from sysinv.common import utils
from sysinv.api.controllers.v1 import utils as apiutils
from sysinv.openstack.common.gettextutils import _


class MACAddressType(wtypes.UserType):
    """A simple MAC address type."""

    basetype = wtypes.text
    name = 'macaddress'

    @staticmethod
    def validate(value):
        return utils.validate_and_normalize_mac(value)

    @staticmethod
    def frombasetype(value):
        return MACAddressType.validate(value)


class UUIDType(wtypes.UserType):
    """A simple UUID type."""

    basetype = wtypes.text
    name = 'uuid'
    # FIXME(lucasagomes): When used with wsexpose decorator WSME will try
    # to get the name of the type by accessing it's __name__ attribute.
    # Remove this __name__ attribute once it's fixed in WSME.
    # https://bugs.launchpad.net/wsme/+bug/1265590
    __name__ = name

    @staticmethod
    def validate(value):
        if not utils.is_uuid_like(value):
            raise exception.InvalidUUID(uuid=value)
        return value

    @staticmethod
    def frombasetype(value):
        if value is None:
            return None
        return UUIDType.validate(value)


class BooleanType(wtypes.UserType):
    """A simple boolean type."""

    basetype = wtypes.text
    name = 'boolean'

    @staticmethod
    def validate(value):
        try:
            return strutils.bool_from_string(value, strict=True)
        except ValueError as e:
            # raise Invalid to return 400 (BadRequest) in the API
            raise exception.Invalid(six.text_type(e))

    @staticmethod
    def frombasetype(value):
        if value is None:
            return None
        return BooleanType.validate(value)


class IPAddressType(wtypes.UserType):
    """A generic IP address type that supports both IPv4 and IPv6."""

    basetype = wtypes.text
    name = 'ipaddress'
    # FIXME(lucasagomes): When used with wsexpose decorator WSME will try
    # to get the name of the type by accessing it's __name__ attribute.
    # Remove this __name__ attribute once it's fixed in WSME.
    # https://bugs.launchpad.net/wsme/+bug/1265590
    __name__ = name

    @staticmethod
    def validate(value):
        if not utils.is_valid_ip(value):
            raise exception.InvalidIPAddress(address=value)
        return value

    @staticmethod
    def frombasetype(value):
        if value is None:
            return None
        return IPAddressType.validate(value)


macaddress = MACAddressType()
uuid = UUIDType()
boolean = BooleanType()
ipaddress = IPAddressType()


class ApiDictType(wtypes.UserType):
    name = 'apidict'
    __name__ = name

    basetype = {wtypes.text: apiutils.ValidTypes(wtypes.text, six.integer_types)}


apidict = ApiDictType()


# TODO(lucasagomes): WSME already has this StringType implementation on trunk,
#                    so remove it on the next WSME release (> 0.5b6)
class StringType(wtypes.UserType):
    """A simple string type. Can validate a length and a pattern.

    :param min_length: Possible minimum length
    :param max_length: Possible maximum length
    :param pattern: Possible string pattern

    Example::

    Name = StringType(min_length=1, pattern='^[a-zA-Z ]*$')

    """
    basetype = six.string_types
    name = "string"

    def __init__(self, min_length=None, max_length=None, pattern=None):
        self.min_length = min_length
        self.max_length = max_length
        if isinstance(pattern, six.string_types):
            self.pattern = re.compile(pattern)
        else:
            self.pattern = pattern

    def validate(self, value):
        if not isinstance(value, self.basetype):
            error = 'Value should be string'
            raise ValueError(error)

        if self.min_length is not None and len(value) < self.min_length:
            error = 'Value should have a minimum character requirement of %s' \
                    % self.min_length
            raise ValueError(error)

        if self.max_length is not None and len(value) > self.max_length:
            error = 'Value should have a maximum character requirement of %s' \
                    % self.max_length
            raise ValueError(error)

        if value != 'nameservers=NC' or value != 'ntpservers=NC':
            if self.pattern is not None and not self.pattern.match(value):
                error = 'Value should match the pattern %s' % self.pattern.pattern
                raise ValueError(error)

        return value


class JsonPatchType(wtypes.Base):
    """A complex type that represents a single json-patch operation."""

    path = wtypes.wsattr(StringType(pattern='^(/[\w-]+)+$'), mandatory=True)
    op = wtypes.wsattr(wtypes.Enum(str, 'add', 'replace', 'remove'),
                       mandatory=True)
    # TODO(jgauld): Should get most recent ironic JsonType/value_types
    value = apiutils.ValidTypes(wtypes.text, six.integer_types, float)

    @staticmethod
    def internal_attrs():
        """Returns a list of internal attributes.

        Internal attributes can't be added, replaced or removed. This
        method may be overwritten by derived class.

        """
        return ['/created_at', '/id', '/links', '/updated_at', '/uuid']

    @staticmethod
    def mandatory_attrs():
        """Retruns a list of mandatory attributes.

        Mandatory attributes can't be removed from the document. This
        method should be overwritten by derived class.

        """
        return []

    @staticmethod
    def validate(patch):
        if patch.path in patch.internal_attrs():
            msg = _("'%s' is an internal attribute and can not be updated")
            raise wsme.exc.ClientSideError(msg % patch.path)

        if patch.path in patch.mandatory_attrs() and patch.op == 'remove':
            msg = _("'%s' is a mandatory attribute and can not be removed")
            raise wsme.exc.ClientSideError(msg % patch.path)

        if patch.op == 'add':
            if patch.path.count('/') == 1:
                msg = _('Adding a new attribute (%s) to the root of '
                        ' the resource is not allowed')
                raise wsme.exc.ClientSideError(msg % patch.path)

        if patch.op != 'remove':
            if not patch.value:
                msg = _("Edit and Add operation of the field requires "
                        "non-empty value.")
                raise wsme.exc.ClientSideError(msg)

        ret = {'path': patch.path, 'op': patch.op}
        if patch.value:
            ret['value'] = patch.value
        return ret


class MultiType(wtypes.UserType):
    """A complex type that represents one or more types.

    Used for validating that a value is an instance of one of the types.

    :param *types: Variable-length list of types.

    """

    def __init__(self, types):
        self.types = types

    def validate(self, value):
        for t in self.types:
            if t is wsme.types.text and isinstance(value, wsme.types.bytes):
                value = value.decode()
            if isinstance(t, list):
                if isinstance(value, list):
                    for v in value:
                        if not isinstance(v, t[0]):
                            break
                    else:
                        return value
            elif isinstance(value, t):
                return value
        else:
            raise ValueError(
                _("Wrong type. Expected '%(type)s', got '%(value)s'")
                % {'type': self.types, 'value': type(value)})
