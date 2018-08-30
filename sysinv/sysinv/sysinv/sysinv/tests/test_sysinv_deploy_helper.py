# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    Copyright (c) 2012 NTT DOCOMO, INC.
#    Copyright 2011 OpenStack Foundation
#    Copyright 2011 Ilya Alekseyev
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

import os
import tempfile
import testtools
import time

import mox

from sysinv.cmd import sysinv_deploy_helper as bmdh
from sysinv import db
from sysinv.openstack.common import log as logging
from sysinv.tests import base as tests_base
from sysinv.tests.db import base

bmdh.LOG = logging.getLogger('sysinv.deploy_helper')

_PXECONF_DEPLOY = """
default deploy

label deploy
kernel deploy_kernel
append initrd=deploy_ramdisk
ipappend 3

label boot
kernel kernel
append initrd=ramdisk root=${ROOT}
"""

_PXECONF_BOOT = """
default boot

label deploy
kernel deploy_kernel
append initrd=deploy_ramdisk
ipappend 3

label boot
kernel kernel
append initrd=ramdisk root=UUID=12345678-1234-1234-1234-1234567890abcdef
"""


class WorkerTestCase(base.DbTestCase):
    def setUp(self):
        super(WorkerTestCase, self).setUp()
        self.worker = bmdh.Worker()
        # Make tearDown() fast
        self.worker.queue_timeout = 0.1
        self.worker.start()

    def tearDown(self):
        if self.worker.isAlive():
            self.worker.stop = True
            self.worker.join(timeout=1)
        # super(WorkerTestCase, self).tearDown()

    def wait_queue_empty(self, timeout):
        for _ in range(int(timeout / 0.1)):
            if bmdh.QUEUE.empty():
                break
            time.sleep(0.1)

    @testtools.skip("not compatible with Sysinv db")
    def test_run_calls_deploy(self):
        """Check all queued requests are passed to deploy()."""
        history = []

        def fake_deploy(**params):
            history.append(params)

        self.stubs.Set(bmdh, 'deploy', fake_deploy)
        self.mox.StubOutWithMock(db, 'bm_node_update')
        # update is called twice inside Worker.run
        for i in range(6):
            db.bm_node_update(mox.IgnoreArg(), mox.IgnoreArg(),
                                        mox.IgnoreArg())
        self.mox.ReplayAll()

        params_list = [{'fake1': ''}, {'fake2': ''}, {'fake3': ''}]
        for (dep_id, params) in enumerate(params_list):
            bmdh.QUEUE.put((dep_id, params))
        self.wait_queue_empty(1)
        self.assertEqual(params_list, history)
        self.mox.VerifyAll()

    @testtools.skip("not compatible with Sysinv db")
    def test_run_with_failing_deploy(self):
        """Check a worker keeps on running even if deploy() raises
        an exception.
        """
        history = []

        def fake_deploy(**params):
            history.append(params)
            # always fail
            raise Exception('test')

        self.stubs.Set(bmdh, 'deploy', fake_deploy)
        self.mox.StubOutWithMock(db, 'bm_node_update')
        # update is called twice inside Worker.run
        for i in range(6):
            db.bm_node_update(mox.IgnoreArg(), mox.IgnoreArg(),
                                        mox.IgnoreArg())
        self.mox.ReplayAll()

        params_list = [{'fake1': ''}, {'fake2': ''}, {'fake3': ''}]
        for (dep_id, params) in enumerate(params_list):
            bmdh.QUEUE.put((dep_id, params))
        self.wait_queue_empty(1)
        self.assertEqual(params_list, history)
        self.mox.VerifyAll()


class PhysicalWorkTestCase(tests_base.TestCase):
    def setUp(self):
        super(PhysicalWorkTestCase, self).setUp()

        def noop(*args, **kwargs):
            pass

        self.stubs.Set(time, 'sleep', noop)

    def test_deploy(self):
        """Check loosely all functions are called with right args."""
        address = '127.0.0.1'
        port = 3306
        iqn = 'iqn.xyz'
        lun = 1
        image_path = '/tmp/xyz/image'
        pxe_config_path = '/tmp/abc/pxeconfig'
        root_mb = 128
        swap_mb = 64

        dev = '/dev/fake'
        root_part = '/dev/fake-part1'
        swap_part = '/dev/fake-part2'
        root_uuid = '12345678-1234-1234-12345678-12345678abcdef'

        self.mox.StubOutWithMock(bmdh, 'get_dev')
        self.mox.StubOutWithMock(bmdh, 'get_image_mb')
        self.mox.StubOutWithMock(bmdh, 'discovery')
        self.mox.StubOutWithMock(bmdh, 'login_iscsi')
        self.mox.StubOutWithMock(bmdh, 'logout_iscsi')
        self.mox.StubOutWithMock(bmdh, 'make_partitions')
        self.mox.StubOutWithMock(bmdh, 'is_block_device')
        self.mox.StubOutWithMock(bmdh, 'dd')
        self.mox.StubOutWithMock(bmdh, 'mkswap')
        self.mox.StubOutWithMock(bmdh, 'block_uuid')
        self.mox.StubOutWithMock(bmdh, 'switch_pxe_config')
        self.mox.StubOutWithMock(bmdh, 'notify')

        bmdh.get_dev(address, port, iqn, lun).AndReturn(dev)
        bmdh.get_image_mb(image_path).AndReturn(1)  # < root_mb
        bmdh.discovery(address, port)
        bmdh.login_iscsi(address, port, iqn)
        bmdh.is_block_device(dev).AndReturn(True)
        bmdh.make_partitions(dev, root_mb, swap_mb)
        bmdh.is_block_device(root_part).AndReturn(True)
        bmdh.is_block_device(swap_part).AndReturn(True)
        bmdh.dd(image_path, root_part)
        bmdh.mkswap(swap_part)
        bmdh.block_uuid(root_part).AndReturn(root_uuid)
        bmdh.logout_iscsi(address, port, iqn)
        bmdh.switch_pxe_config(pxe_config_path, root_uuid)
        bmdh.notify(address, 10000)
        self.mox.ReplayAll()

        bmdh.deploy(address, port, iqn, lun, image_path, pxe_config_path,
                    root_mb, swap_mb)

        self.mox.VerifyAll()

    def test_always_logout_iscsi(self):
        """logout_iscsi() must be called once login_iscsi() is called."""
        address = '127.0.0.1'
        port = 3306
        iqn = 'iqn.xyz'
        lun = 1
        image_path = '/tmp/xyz/image'
        pxe_config_path = '/tmp/abc/pxeconfig'
        root_mb = 128
        swap_mb = 64

        dev = '/dev/fake'

        self.mox.StubOutWithMock(bmdh, 'get_dev')
        self.mox.StubOutWithMock(bmdh, 'get_image_mb')
        self.mox.StubOutWithMock(bmdh, 'discovery')
        self.mox.StubOutWithMock(bmdh, 'login_iscsi')
        self.mox.StubOutWithMock(bmdh, 'logout_iscsi')
        self.mox.StubOutWithMock(bmdh, 'work_on_disk')

        class TestException(Exception):
            pass

        bmdh.get_dev(address, port, iqn, lun).AndReturn(dev)
        bmdh.get_image_mb(image_path).AndReturn(1)  # < root_mb
        bmdh.discovery(address, port)
        bmdh.login_iscsi(address, port, iqn)
        bmdh.work_on_disk(dev, root_mb, swap_mb, image_path).\
                AndRaise(TestException)
        bmdh.logout_iscsi(address, port, iqn)
        self.mox.ReplayAll()

        self.assertRaises(TestException,
                         bmdh.deploy,
                         address, port, iqn, lun, image_path,
                         pxe_config_path, root_mb, swap_mb)


class SwitchPxeConfigTestCase(tests_base.TestCase):
    def setUp(self):
        super(SwitchPxeConfigTestCase, self).setUp()
        (fd, self.fname) = tempfile.mkstemp()
        os.write(fd, _PXECONF_DEPLOY)
        os.close(fd)

    def tearDown(self):
        os.unlink(self.fname)
        super(SwitchPxeConfigTestCase, self).tearDown()

    def test_switch_pxe_config(self):
        bmdh.switch_pxe_config(self.fname,
                               '12345678-1234-1234-1234-1234567890abcdef')
        with open(self.fname, 'r') as f:
            pxeconf = f.read()
        self.assertEqual(pxeconf, _PXECONF_BOOT)


class OtherFunctionTestCase(tests_base.TestCase):
    def test_get_dev(self):
        expected = '/dev/disk/by-path/ip-1.2.3.4:5678-iscsi-iqn.fake-lun-9'
        actual = bmdh.get_dev('1.2.3.4', 5678, 'iqn.fake', 9)
        self.assertEqual(expected, actual)

    def test_get_image_mb(self):
        mb = 1024 * 1024
        size = None

        def fake_getsize(path):
            return size

        self.stubs.Set(os.path, 'getsize', fake_getsize)
        size = 0
        self.assertEqual(bmdh.get_image_mb('x'), 0)
        size = 1
        self.assertEqual(bmdh.get_image_mb('x'), 1)
        size = mb
        self.assertEqual(bmdh.get_image_mb('x'), 1)
        size = mb + 1
        self.assertEqual(bmdh.get_image_mb('x'), 2)
