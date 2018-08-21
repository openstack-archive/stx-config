#!/usr/bin/env python

# Copyright (c) 2012 NTT DOCOMO, INC.
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
# Copyright (c) 2013-2016 Wind River Systems, Inc.
#


"""Starter script for Bare-Metal Deployment Service."""


import os
import sys
import threading
import time

import cgi
import Queue
import re
import socket
import stat
from wsgiref import simple_server

from sysinv.common import config
from sysinv.common import exception
from sysinv.common import states
from sysinv.common import utils
from sysinv import db
from sysinv.openstack.common import context as sysinv_context
from sysinv.openstack.common import excutils
from sysinv.openstack.common.gettextutils import _
from sysinv.openstack.common import log as logging


QUEUE = Queue.Queue()
LOG = logging.getLogger(__name__)


# All functions are called from deploy() directly or indirectly.
# They are split for stub-out.

def discovery(portal_address, portal_port):
    """Do iSCSI discovery on portal."""
    utils.execute('iscsiadm',
                  '-m', 'discovery',
                  '-t', 'st',
                  '-p', '%s:%s' % (portal_address, portal_port),
                  run_as_root=True,
                  check_exit_code=[0])


def login_iscsi(portal_address, portal_port, target_iqn):
    """Login to an iSCSI target."""
    utils.execute('iscsiadm',
                  '-m', 'node',
                  '-p', '%s:%s' % (portal_address, portal_port),
                  '-T', target_iqn,
                  '--login',
                  run_as_root=True,
                  check_exit_code=[0])
    # Ensure the login complete
    time.sleep(3)


def logout_iscsi(portal_address, portal_port, target_iqn):
    """Logout from an iSCSI target."""
    utils.execute('iscsiadm',
                  '-m', 'node',
                  '-p', '%s:%s' % (portal_address, portal_port),
                  '-T', target_iqn,
                  '--logout',
                  run_as_root=True,
                  check_exit_code=[0])


def make_partitions(dev, root_mb, swap_mb):
    """Create partitions for root and swap on a disk device."""
    # Lead in with 1MB to allow room for the partition table itself, otherwise
    # the way sfdisk adjusts doesn't shift the partition up to compensate, and
    # we lose the space.
    # http://bazaar.launchpad.net/~ubuntu-branches/ubuntu/raring/util-linux/
    # raring/view/head:/fdisk/sfdisk.c#L1940
    stdin_command = ('1,%d,83;\n,%d,82;\n0,0;\n0,0;\n' % (root_mb, swap_mb))
    utils.execute('sfdisk', '-uM', dev, process_input=stdin_command,
                  run_as_root=True,
                  attempts=3,
                  check_exit_code=[0])
    # avoid "device is busy"
    time.sleep(3)


def is_block_device(dev):
    """Check whether a device is block or not."""
    s = os.stat(dev)
    return stat.S_ISBLK(s.st_mode)


def dd(src, dst):
    """Execute dd from src to dst."""
    utils.execute('dd',
                  'if=%s' % src,
                  'of=%s' % dst,
                  'bs=1M',
                  'oflag=direct',
                  run_as_root=True,
                  check_exit_code=[0])


def mkswap(dev, label='swap1'):
    """Execute mkswap on a device."""
    utils.execute('mkswap',
                  '-L', label,
                  dev,
                  run_as_root=True,
                  check_exit_code=[0])


def block_uuid(dev):
    """Get UUID of a block device."""
    out, _ = utils.execute('blkid', '-s', 'UUID', '-o', 'value', dev,
                           run_as_root=True,
                           check_exit_code=[0])
    return out.strip()


def switch_pxe_config(path, root_uuid):
    """Switch a pxe config from deployment mode to service mode."""
    with open(path) as f:
        lines = f.readlines()
    root = 'UUID=%s' % root_uuid
    rre = re.compile(r'\$\{ROOT\}')
    dre = re.compile('^default .*$')
    with open(path, 'w') as f:
        for line in lines:
            line = rre.sub(root, line)
            line = dre.sub('default boot', line)
            f.write(line)


def notify(address, port):
    """Notify a node that it becomes ready to reboot."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((address, port))
        s.send('done')
    finally:
        s.close()


def get_dev(address, port, iqn, lun):
    """Returns a device path for given parameters."""
    dev = "/dev/disk/by-path/ip-%s:%s-iscsi-%s-lun-%s" \
        % (address, port, iqn, lun)
    return dev


def get_image_mb(image_path):
    """Get size of an image in Megabyte."""
    mb = 1024 * 1024
    image_byte = os.path.getsize(image_path)
    # round up size to MB
    image_mb = int((image_byte + mb - 1) / mb)
    return image_mb


def work_on_disk(dev, root_mb, swap_mb, image_path):
    """Creates partitions and write an image to the root partition."""
    root_part = "%s-part1" % dev
    swap_part = "%s-part2" % dev

    if not is_block_device(dev):
        LOG.warn(_("parent device '%s' not found") % dev)
        return
    make_partitions(dev, root_mb, swap_mb)
    if not is_block_device(root_part):
        LOG.warn(_("root device '%s' not found") % root_part)
        return
    if not is_block_device(swap_part):
        LOG.warn(_("swap device '%s' not found") % swap_part)
        return
    dd(image_path, root_part)
    mkswap(swap_part)

    try:
        root_uuid = block_uuid(root_part)
    except exception.ProcessExecutionError:
        with excutils.save_and_reraise_exception():
            LOG.error("Failed to detect root device UUID.")
    return root_uuid


def deploy(address, port, iqn, lun, image_path, pxe_config_path,
           root_mb, swap_mb):
    """All-in-one function to deploy a node."""
    dev = get_dev(address, port, iqn, lun)
    image_mb = get_image_mb(image_path)
    if image_mb > root_mb:
        root_mb = image_mb
    discovery(address, port)
    login_iscsi(address, port, iqn)
    try:
        root_uuid = work_on_disk(dev, root_mb, swap_mb, image_path)
    except exception.ProcessExecutionError as err:
        with excutils.save_and_reraise_exception():
            # Log output if there was a error
            LOG.error("Cmd     : %s" % err.cmd)
            LOG.error("StdOut  : %s" % err.stdout)
            LOG.error("StdErr  : %s" % err.stderr)
    finally:
        logout_iscsi(address, port, iqn)
    switch_pxe_config(pxe_config_path, root_uuid)
    # Ensure the node started netcat on the port after POST the request.
    time.sleep(3)
    notify(address, 10000)


class Worker(threading.Thread):
    """Thread that handles requests in queue."""

    def __init__(self):
        super(Worker, self).__init__()
        self.setDaemon(True)
        self.stop = False
        self.queue_timeout = 1

    def run(self):
        while not self.stop:
            try:
                # Set timeout to check self.stop periodically
                (node_id, params) = QUEUE.get(block=True,
                                              timeout=self.queue_timeout)
            except Queue.Empty:
                pass
            else:
                # Requests comes here from BareMetalDeploy.post()
                LOG.info(_('start deployment for node %(node_id)s, '
                           'params %(params)s') %
                         {'node_id': node_id, 'params': params})
                context = sysinv_context.get_admin_context()
                try:
                    db.bm_node_update(context, node_id,
                                      {'task_state': states.DEPLOYING})
                    deploy(**params)
                except Exception:
                    LOG.error(_('deployment to node %s failed') % node_id)
                    db.bm_node_update(context, node_id,
                                      {'task_state': states.DEPLOYFAIL})
                else:
                    LOG.info(_('deployment to node %s done') % node_id)
                    db.bm_node_update(context, node_id,
                                      {'task_state': states.DEPLOYDONE})


class BareMetalDeploy(object):
    """WSGI server for bare-metal deployment."""

    def __init__(self):
        self.worker = Worker()
        self.worker.start()

    def __call__(self, environ, start_response):
        method = environ['REQUEST_METHOD']
        if method == 'POST':
            return self.post(environ, start_response)
        else:
            start_response('501 Not Implemented',
                           [('Content-type', 'text/plain')])
            return 'Not Implemented'

    def post(self, environ, start_response):
        LOG.info(_("post: environ=%s") % environ)
        inpt = environ['wsgi.input']
        length = int(environ.get('CONTENT_LENGTH', 0))

        x = inpt.read(length)
        q = dict(cgi.parse_qsl(x))
        try:
            node_id = q['i']
            deploy_key = q['k']
            address = q['a']
            port = q.get('p', '3260')
            iqn = q['n']
            lun = q.get('l', '1')
            err_msg = q.get('e')
        except KeyError as e:
            start_response('400 Bad Request', [('Content-type', 'text/plain')])
            return "parameter '%s' is not defined" % e

        if err_msg:
            LOG.error(_('Deploy agent error message: %s'), err_msg)

        context = sysinv_context.get_admin_context()
        d = db.bm_node_get(context, node_id)

        if d['deploy_key'] != deploy_key:
            start_response('400 Bad Request', [('Content-type', 'text/plain')])
            return 'key is not match'

        params = {'address': address,
                  'port': port,
                  'iqn': iqn,
                  'lun': lun,
                  'image_path': d['image_path'],
                  'pxe_config_path': d['pxe_config_path'],
                  'root_mb': int(d['root_mb']),
                  'swap_mb': int(d['swap_mb']),
                  }
        # Restart worker, if needed
        if not self.worker.isAlive():
            self.worker = Worker()
            self.worker.start()
        LOG.info(_("request is queued: node %(node_id)s, params %(params)s") %
                 {'node_id': node_id, 'params': params})
        QUEUE.put((node_id, params))
        # Requests go to Worker.run()
        start_response('200 OK', [('Content-type', 'text/plain')])
        return ''


def main():
    config.parse_args(sys.argv)
    logging.setup("nova")
    global LOG
    LOG = logging.getLogger('nova.virt.baremetal.deploy_helper')
    app = BareMetalDeploy()
    srv = simple_server.make_server('', 10000, app)
    srv.serve_forever()
