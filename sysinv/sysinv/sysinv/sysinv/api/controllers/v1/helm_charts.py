#
# Copyright (c) 2018 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

import os
import pecan
from pecan import rest
import subprocess
import tempfile

import wsme
from wsme import types as wtypes
import wsmeext.pecan as wsme_pecan

from sysinv import objects
from sysinv.common import exception
from sysinv.openstack.common import log
from sysinv.openstack.common.gettextutils import _


LOG = log.getLogger(__name__)

SYSTEM_CHARTS = ['mariadb', 'rabbitmq', 'ingress']


class HelmChartsController(rest.RestController):

    @wsme_pecan.wsexpose(wtypes.text)
    def get_all(self):
        """Provides information about the available charts to override."""

        overrides = pecan.request.dbapi.helm_override_get_all()

        charts = [{'name': chart, 'namespaces': []} for chart in SYSTEM_CHARTS]
        for chart in charts:
            namespaces = [x['namespace'] for x in overrides
                          if x['name'] == chart['name']]
            chart['namespaces'] = namespaces
        return {'charts': charts}

    @wsme_pecan.wsexpose(wtypes.text, wtypes.text, wtypes.text)
    def get_one(self, name, namespace):
        """Retrieve information about the given event_log.

        :param name: name of helm chart
        :param namespace: namespace of chart overrides
        """
        try:
            db_chart = objects.helm_overrides.get_by_name(
                pecan.request.context, name, namespace)
            overrides = db_chart.user_overrides
        except exception.HelmOverrideNotFound:
            if name in SYSTEM_CHARTS:
                overrides = {}
            else:
                raise

        rpc_chart = {'name': name,
                     'namespace': namespace,
                     'system_overrides': {},
                     'user_overrides': overrides}

        return rpc_chart

    def validate_name_and_namespace(self, name, namespace):
        if not name:
                raise wsme.exc.ClientSideError(_(
                    "Helm-override-update rejected: name must be specified"))
        if not namespace:
            raise wsme.exc.ClientSideError(_(
                "Helm-override-update rejected: namespace must be specified"))

    @wsme_pecan.wsexpose(wtypes.text, wtypes.text, wtypes.text, wtypes.text, wtypes.text)
    def patch(self, name, namespace, flag, values):
        """ Update user overrides.

        :param name: chart name
        :param namespace: namespace of chart overrides
        :param flag: one of "reuse" or "reset", describes how to handle
                     previous user overrides
        :param values: a dict of different types of user override values
        """
        self.validate_name_and_namespace(name, namespace)

        try:
            db_chart = objects.helm_overrides.get_by_name(
                pecan.request.context, name, namespace)
            db_values = db_chart.user_overrides  # noqa
        except exception.HelmOverrideNotFound:
            if name in SYSTEM_CHARTS:
                pecan.request.dbapi.helm_override_create({
                    'name': name,
                    'namespace': namespace,
                    'user_overrides': ''})
                db_chart = objects.helm_overrides.get_by_name(
                    pecan.request.context, name, namespace)
            else:
                raise
        db_values = db_chart.user_overrides

        # At this point we have potentially two separate types of overrides
        # specified by the user, values from files and values passed in via
        # --set .  We need to ensure that we call helm using the same
        # mechanisms to ensure the same behaviour.
        cmd = ['helm', 'install', '--dry-run', '--debug']

        if flag == 'reuse':
            values['files'].insert(0, db_values)
        elif flag == 'reset':
            pass
        else:
            raise wsme.exc.ClientSideError(_("Invalid flag: %s must be either "
                                             "'reuse' or 'reset'.") % flag)

        # Now process the newly-passed-in override values
        tmpfiles = []
        for value_file in values['files']:
            # For values passed in from files, write them back out to
            # temporary files.
            tmpfile = tempfile.NamedTemporaryFile(delete=False)
            tmpfile.write(value_file)
            tmpfile.close()
            tmpfiles.append(tmpfile.name)
            cmd.extend(['--values', tmpfile.name])

        for value_set in values['set']:
            cmd.extend(['--set', value_set])

        env = os.environ.copy()
        env['KUBECONFIG'] = '/etc/kubernetes/admin.conf'

        # Make a temporary directory with a fake chart in it
        try:
            tmpdir = tempfile.mkdtemp()
            chartfile = tmpdir + '/Chart.yaml'
            with open(chartfile, 'w') as tmpchart:
                tmpchart.write('name: mychart\napiVersion: v1\n'
                               'version: 0.1.0\n')
            cmd.append(tmpdir)

            # Apply changes by calling out to helm to do values merge
            # using a dummy chart.
            # NOTE: this requires running sysinv-api as root, will fix it
            # to use RPC in a followup patch.
            output = subprocess.check_output(cmd, env=env)

            # Check output for failure

            # Extract the info we want.
            values = output.split('USER-SUPPLIED VALUES:\n')[1].split(
                                  '\nCOMPUTED VALUES:')[0]
        except exception.SysinvException:
            raise
        finally:
            os.remove(chartfile)
            os.rmdir(tmpdir)

        for tmpfile in tmpfiles:
            os.remove(tmpfile)

        # save chart overrides back to DB
        db_chart.user_overrides = values
        db_chart.save()

        chart = {'name': name, 'namespace': namespace,
                 'user_overrides': values}

        return chart

    @wsme_pecan.wsexpose(None, wtypes.text, wtypes.text, status_code=204)
    def delete(self, name, namespace):
        """Delete user overrides for a chart

        :param name: chart name.
        :param namespace: namespace of chart overrides
        """
        self.validate_name_and_namespace(name, namespace)
        try:
            pecan.request.dbapi.helm_override_destroy(name, namespace)
        except exception.HelmOverrideNotFound:
            pass
