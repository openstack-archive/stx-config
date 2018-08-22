########################################################################
#
# Copyright (c) 2018 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#
########################################################################

import jsonpatch

import pecan
from pecan import rest

import wsme
from wsme import types as wtypes
import wsmeext.pecan as wsme_pecan

from sysinv.api.controllers.v1 import base
from sysinv.api.controllers.v1 import collection
from sysinv.api.controllers.v1 import link
from sysinv.api.controllers.v1 import types
from sysinv.api.controllers.v1 import utils
from sysinv.common import exception
from sysinv.common import utils as cutils
from sysinv import objects
from sysinv.openstack.common.gettextutils import _
from sysinv.openstack.common import log


LOG = log.getLogger(__name__)


class PTPPatchType(types.JsonPatchType):

    @staticmethod
    def mandatory_attrs():
        return []


class PTP(base.APIBase):
    """API representation of PTP configuration.

    This class enforces type checking and value constraints, and converts
    between the internal object model and the API representation of
    an ptp.
    """

    uuid = types.uuid
    "Unique UUID for this ptp"

    enabled = types.boolean
    "Represent the status of the ptp."

    mode = wtypes.Enum(str, 'hardware', 'software', 'legacy')
    "Time stamping mode used by ptp."

    transport = wtypes.Enum(str, 'l2', 'udp')
    "Network transport used by ptp."

    mechanism = wtypes.Enum(str, 'e2e', 'p2p')
    "Messaging mechanism used by ptp."

    links = [link.Link]
    "A list containing a self link and associated ptp links"

    isystem_uuid = types.uuid
    "The UUID of the system this ptp belongs to"

    created_at = wtypes.datetime.datetime
    updated_at = wtypes.datetime.datetime

    def __init__(self, **kwargs):
        self.fields = objects.ptp.fields.keys()
        for k in self.fields:
            setattr(self, k, kwargs.get(k))

    @classmethod
    def convert_with_links(cls, rpc_ptp, expand=True):

        ptp = PTP(**rpc_ptp.as_dict())
        if not expand:
            ptp.unset_fields_except(['uuid',
                                     'enabled',
                                     'mode',
                                     'transport',
                                     'mechanism',
                                     'isystem_uuid',
                                     'created_at',
                                     'updated_at'])

        ptp.links = [link.Link.make_link('self', pecan.request.host_url,
                                         'ptps', ptp.uuid),
                     link.Link.make_link('bookmark',
                                         pecan.request.host_url,
                                         'ptps', ptp.uuid,
                                         bookmark=True)
                     ]

        return ptp


class ptpCollection(collection.Collection):
    """API representation of a collection of ptps."""

    ptps = [PTP]
    "A list containing ptp objects"

    def __init__(self, **kwargs):
        self._type = 'ptps'

    @classmethod
    def convert_with_links(cls, rpc_ptps, limit, url=None,
                           expand=False, **kwargs):
        collection = ptpCollection()
        collection.ptps = [PTP.convert_with_links(p, expand)
                            for p in rpc_ptps]
        collection.next = collection.get_next(limit, url=url, **kwargs)
        return collection


##############
# UTILS
##############
def _check_ptp_data(op, ptp):
    enabled = ptp['enabled']
    ntp_list = pecan.request.dbapi.intp_get_by_isystem(ptp['isystem_uuid'])
    if ntp_list:
        if hasattr(ntp_list[0], 'enabled'):
            if ntp_list[0].enabled is True and enabled is True:
                    raise wsme.exc.ClientSideError(_(
                        "PTP cannot be configured alongside with NTP."
                        " Please disable NTP before enabling PTP."))
    return ptp


LOCK_NAME = 'PTPController'


class PTPController(rest.RestController):
    """REST controller for ptps."""

    _custom_actions = {
        'detail': ['GET'],
    }

    def _get_ptps_collection(self, marker, limit, sort_key, sort_dir,
                             expand=False, resource_url=None):

        limit = utils.validate_limit(limit)
        sort_dir = utils.validate_sort_dir(sort_dir)

        marker_obj = None
        if marker:
            marker_obj = objects.ptp.get_by_uuid(pecan.request.context,
                                                 marker)

        ptps = pecan.request.dbapi.ptp_get_list(limit, marker_obj,
                                                     sort_key=sort_key,
                                                     sort_dir=sort_dir)

        return ptpCollection.convert_with_links(ptps, limit,
                                                 url=resource_url,
                                                 expand=expand,
                                                 sort_key=sort_key,
                                                 sort_dir=sort_dir)

    @wsme_pecan.wsexpose(ptpCollection, types.uuid, int,
                         wtypes.text, wtypes.text)
    def get_all(self, marker=None, limit=None,
                sort_key='id', sort_dir='asc'):
        """Retrieve a list of ptps. Only one per system"""

        return self._get_ptps_collection(marker, limit,
                                         sort_key, sort_dir)

    @wsme_pecan.wsexpose(ptpCollection, types.uuid, int,
                         wtypes.text, wtypes.text)
    def detail(self, marker=None, limit=None,
               sort_key='id', sort_dir='asc'):
        """Retrieve a list of ptps with detail."""
        # NOTE(lucasagomes): /detail should only work agaist collections
        parent = pecan.request.path.split('/')[:-1][-1]
        if parent != "ptps":
            raise exception.HTTPNotFound

        expand = True
        resource_url = '/'.join(['ptps', 'detail'])
        return self._get_ptps_collection(marker, limit,
                                         sort_key, sort_dir,
                                         expand, resource_url)

    @wsme_pecan.wsexpose(PTP, types.uuid)
    def get_one(self, ptp_uuid):
        """Retrieve information about the given ptp."""
        rpc_ptp = objects.ptp.get_by_uuid(pecan.request.context, ptp_uuid)
        return PTP.convert_with_links(rpc_ptp)

    @wsme_pecan.wsexpose(PTP, body=PTP)
    def post(self, ptp):
        """Create a new ptp."""
        raise exception.OperationNotPermitted

    @cutils.synchronized(LOCK_NAME)
    @wsme.validate(types.uuid, [PTPPatchType])
    @wsme_pecan.wsexpose(PTP, types.uuid,
                         body=[PTPPatchType])
    def patch(self, ptp_uuid, patch):
        """Update the current PTP configuration."""

        rpc_ptp = objects.ptp.get_by_uuid(pecan.request.context, ptp_uuid)
        patch_obj = jsonpatch.JsonPatch(patch)

        state_rel_path = ['/uuid', '/id']
        if any(p['path'] in state_rel_path for p in patch_obj):
            raise wsme.exc.ClientSideError(_("The following fields can not be "
                                             "modified: %s" %
                                             state_rel_path))

        try:
            ptp = PTP(**jsonpatch.apply_patch(rpc_ptp.as_dict(),
                                              patch_obj))

        except utils.JSONPATCH_EXCEPTIONS as e:
            raise exception.PatchError(patch=patch, reason=e)

        ptp = _check_ptp_data("modify", ptp.as_dict())

        try:
            # Update only the fields that have changed
            for field in objects.ptp.fields:
                if rpc_ptp[field] != ptp[field]:
                    rpc_ptp[field] = ptp[field]

            delta = rpc_ptp.obj_what_changed()
            if delta:
                rpc_ptp.save()
                # perform rpc to conductor to perform config apply
                pecan.request.rpcapi.update_ptp_config(pecan.request.context)
            else:
                LOG.info("No PTP config changes")

            return PTP.convert_with_links(rpc_ptp)

        except exception.HTTPNotFound:
            msg = _("PTP update failed: enabled %s : %s %s %s : patch %s"
                        % (ptp['enabled'], ptp['mode'], ptp['transport'],
                           ptp['mechanism'], patch))
            raise wsme.exc.ClientSideError(msg)

    @wsme_pecan.wsexpose(None, types.uuid, status_code=204)
    def delete(self, ptp_uuid):
        """Delete a ptp."""
        raise exception.OperationNotPermitted
