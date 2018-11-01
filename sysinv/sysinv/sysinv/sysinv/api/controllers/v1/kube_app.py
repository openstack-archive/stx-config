#
# Copyright (c) 2018 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

import os
import pecan
from pecan import rest
import shutil
import subprocess
import tarfile
import tempfile
import wsme
from wsme import types as wtypes
import wsmeext.pecan as wsme_pecan

import yaml

from contextlib import contextmanager
from sysinv import objects
from sysinv.api.controllers.v1 import base
from sysinv.api.controllers.v1 import collection
from sysinv.api.controllers.v1 import types
from sysinv.common import constants
from sysinv.common import exception
from sysinv.common import utils as cutils
from sysinv.openstack.common import log
from sysinv.openstack.common.gettextutils import _


LOG = log.getLogger(__name__)


@contextmanager
def TempDirectory():
    tmpdir = tempfile.mkdtemp()
    saved_umask = os.umask(0077)
    try:
        yield tmpdir
    finally:
        LOG.info("Cleaning up temp directory %s" % tmpdir)
        os.umask(saved_umask)
        shutil.rmtree(tmpdir)


class KubeApp(base.APIBase):
    """API representation of a containerized application."""

    id = int
    "Unique ID for this application"

    name = wtypes.text
    "Represents the name of the application"

    created_at = wtypes.datetime.datetime
    "Represents the time the application was uploaded"

    updated_at = wtypes.datetime.datetime
    "Represents the time the application was updated"

    manifest_name = wtypes.text
    "Represents the name of the application manifest"

    manifest_file = wtypes.text
    "Represents the filename of the application manifest"

    status = wtypes.text
    "Represents the installation status of the application"

    def __init__(self, **kwargs):
        self.fields = objects.kube_app.fields.keys()
        for k in self.fields:
            if not hasattr(self, k):
                continue
            setattr(self, k, kwargs.get(k, wtypes.Unset))

    @classmethod
    def convert_with_links(cls, rpc_app, expand=True):
        app = KubeApp(**rpc_app.as_dict())
        if not expand:
            app.unset_fields_except(['name', 'updated_time', 'status'])

        # skip the id
        app.id = wtypes.Unset

        return app


class KubeAppCollection(collection.Collection):
    """API representation of a collection of Helm applications."""

    apps = [KubeApp]
    "A list containing application objects"

    def __init__(self, **kwargs):
        self._type = 'apps'

    @classmethod
    def convert_with_links(cls, rpc_apps, limit, url=None,
                           expand=False, **kwargs):
        collection = KubeAppCollection()
        collection.apps = [KubeApp.convert_with_links(n, expand)
                             for n in rpc_apps]
        collection.next = collection.get_next(limit, url=url, **kwargs)
        return collection


LOCK_NAME = 'KubeAppController'


class KubeAppController(rest.RestController):
    """REST controller for Helm applications."""

    def __init__(self, parent=None, **kwargs):
        self._parent = parent

    def _check_tarfile(self, app_name, app_tarfile):
        if app_name and app_tarfile:
            if not os.path.isfile(app_tarfile):
                raise wsme.exc.ClientSideError(_(
                    "Application-upload rejected: application tar file %s does "
                    "not exist." % app_tarfile))
            if (not app_tarfile.endswith('.tgz') and
                    not app_tarfile.endswith('.tar.gz')):
                raise wsme.exc.ClientSideError(_(
                    "Application-upload rejected: %s is not a tar file" %
                    app_tarfile))

            with TempDirectory() as app_path:
                try:
                    tar = tarfile.open(app_tarfile, 'r:gz')
                    tar.extractall(path=app_path)
                    # If checksum file is included in the tarball, verify
                    # its content.
                    if not self._verify_checksum(app_path):
                        raise wsme.exc.ClientSideError(_(
                            "Application-upload rejected: checksum validation "
                            "failed."))
                    mname, mfile = self._find_manifest_file(app_path)
                    if not mfile:
                        raise wsme.exc.ClientSideError(_(
                            "Application-upload rejected: manifest file is "
                            "missing."))
                    charts_dir = os.path.join(app_path, 'charts')
                    if os.path.isdir(charts_dir):
                        tar_filelist = cutils.get_files_matching(app_path,
                                                                 '.tgz')
                        if (len(os.listdir(charts_dir)) == 0 or
                                not tar_filelist):
                            raise wsme.exc.ClientSideError(_(
                                "Application-upload rejected: tar file "
                                "contains no Helm charts."))
                        for p, f in tar_filelist:
                            tar = tarfile.open(os.path.join(p, f), 'r:gz')
                            tar.extractall(p)
                    return mname, mfile
                except OSError as e:
                    LOG.error("Error while extracting tar file %s for "
                              "application %s: %s" % (app_tarfile, app_name, e))
                    raise wsme.exc.ClientSideError(_(
                        "Application-upload rejected: failed to extract tar file "
                        "%s." % app_tarfile))
        else:
            raise ValueError(_(
                "Application-upload rejected: both application name and tar "
                "file must be specified."))

        LOG.info("Tar file of application %s extracted." % app_name)
        return app_path

    def _verify_checksum(self, app_path):
        rc = True
        for file in os.listdir(app_path):
            if file.endswith('.md5'):
                cwd = os.getcwd()
                os.chdir(app_path)
                with open(os.devnull, "w") as fnull:
                    try:
                        subprocess.check_call(['md5sum', '-c', file],
                                              stdout=fnull, stderr=fnull)
                        LOG.info("Checksum file is included and validated.")
                    except subprocess.CalledProcessError as e:
                        LOG.exception(e)
                        rc = False
                    finally:
                        os.chdir(cwd)
                        return rc

        # Do we need to make the inclusion of md5 file a hard requirement?
        LOG.info("Checksum file is not included, skipping validation.")
        return rc

    def _find_manifest_file(self, app_path):
        # It is expected that there is only one manifest file
        # per application and the file exists at top level of
        # the application path.
        for file in os.listdir(app_path):
            if file.endswith('.yaml'):
                yaml_file = os.path.join(app_path, file)
                with open(yaml_file, 'r') as f:
                    docs = yaml.load_all(f)
                    for doc in docs:
                        try:
                            if "armada/Manifest" in doc['schema']:
                                manifest_name = doc['metadata']['name']
                                return manifest_name, yaml_file
                        except KeyError:
                            # Could be some other yaml files
                            pass
        return None, None

    def _get_one(self, app_name):
        # can result in KubeAppNotFound
        kube_app = objects.kube_app.get_by_name(
            pecan.request.context, app_name)
        return KubeApp.convert_with_links(kube_app)

    @wsme_pecan.wsexpose(KubeAppCollection)
    def get_all(self):
        apps = pecan.request.dbapi.kube_app_get_all()
        collection = KubeAppCollection()
        collection.apps = [KubeApp.convert_with_links(app)
                           for app in apps]
        return collection

    @wsme_pecan.wsexpose(KubeApp, wtypes.text)
    def get_one(self, app_name):
        """Retrieve a single application."""
        return self._get_one(app_name)

    @cutils.synchronized(LOCK_NAME)
    @wsme_pecan.wsexpose(KubeApp, body=types.apidict)
    def post(self, body):
        """Uploading an application to be deployed by Armada"""

        name = body.get('name')
        tarfile = body.get('tarfile')

        try:
            objects.kube_app.get_by_name(pecan.request.context, name)
            raise wsme.exc.ClientSideError(_(
                "Application-upload rejected: application %s already exists." %
                name))
        except exception.KubeAppNotFound:
            pass

        mname, mfile = self._check_tarfile(name, tarfile)

        # Create a database entry and make an rpc async request to upload
        # the application
        app_data = {'name': name,
                    'manifest_name': mname,
                    'manifest_file': os.path.basename(mfile),
                    'status': constants.APP_UPLOAD_IN_PROGRESS}
        try:
            new_app = pecan.request.dbapi.kube_app_create(app_data)
        except exception.SysinvException as e:
            LOG.exception(e)
            raise

        pecan.request.rpcapi.perform_app_upload(pecan.request.context,
                                                new_app, tarfile)
        return KubeApp.convert_with_links(new_app)

    @cutils.synchronized(LOCK_NAME)
    @wsme_pecan.wsexpose(KubeApp, wtypes.text, wtypes.text, wtypes.text)
    def patch(self, name, directive, values):
        """Install/update the specified application

        :param name: application name
        :param directive: either 'apply' (fresh install/update) or 'remove'
        """

        if directive not in ['apply', 'remove']:
            raise exception.OperationNotPermitted

        try:
            db_app = objects.kube_app.get_by_name(pecan.request.context, name)
        except exception.KubeAppNotFound:
            LOG.error("Received a request to %s app %s which does not exist." %
                      (directive, name))
            raise wsme.exc.ClientSideError(_(
                "Application-%s rejected: application not found." % directive))

        if directive == 'apply':
            if db_app.status == constants.APP_APPLY_IN_PROGRESS:
                raise wsme.exc.ClientSideError(_(
                    "Application-apply rejected: install/update is already "
                    "in progress."))
            elif db_app.status not in [constants.APP_UPLOAD_SUCCESS,
                                       constants.APP_APPLY_FAILURE,
                                       constants.APP_APPLY_SUCCESS]:
                raise wsme.exc.ClientSideError(_(
                    "Application-apply rejected: operation is not allowed "
                    "while the current status is %s." % db_app.status))
            db_app.status = constants.APP_APPLY_IN_PROGRESS
            db_app.save()
            pecan.request.rpcapi.perform_app_apply(pecan.request.context,
                                                   db_app)
            return KubeApp.convert_with_links(db_app)
        else:
            if db_app.status not in [constants.APP_APPLY_SUCCESS,
                                     constants.APP_APPLY_FAILURE]:
                raise wsme.exc.ClientSideError(_(
                    "Application-remove rejected: operation is not allowed while "
                    "the current status is %s." % db_app.status))
            db_app.status = constants.APP_REMOVE_IN_PROGRESS
            db_app.save()
            pecan.request.rpcapi.perform_app_remove(pecan.request.context,
                                                    db_app)
            return KubeApp.convert_with_links(db_app)

    @cutils.synchronized(LOCK_NAME)
    @wsme_pecan.wsexpose(None, wtypes.text, status_code=204)
    def delete(self, name):
        """Delete the application with the given name

        :param name: application name
        """

        try:
            db_app = objects.kube_app.get_by_name(pecan.request.context, name)
        except exception.KubeAppNotFound:
            LOG.error("Received a request to delete app %s which does not "
                      "exist." % name)
            raise

        response = pecan.request.rpcapi.perform_app_delete(
            pecan.request.context, db_app)
        if response:
            raise wsme.exc.ClientSideError(_(
                "%s." % response))
