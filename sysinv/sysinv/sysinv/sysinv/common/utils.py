# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# Copyright 2011 Justin Santa Barbara
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
# Copyright (c) 2013-2018 Wind River Systems, Inc.
#


"""Utilities and helper functions."""

import collections
import contextlib
import datetime
import errno
import functools
import fcntl
import glob
import grp
import hashlib
import itertools as it
import json
import math
import os
import pwd
import random
import re
import shutil
import signal
import six
import socket
import tempfile
import time
import uuid
import wsme

from eventlet.green import subprocess
from eventlet import greenthread
import netaddr

from oslo_config import cfg

from sysinv.common import exception
from sysinv.common import constants
from sysinv.openstack.common import log as logging
from sysinv.openstack.common.gettextutils import _
from oslo_concurrency import lockutils


try:
    from tsconfig.tsconfig import SW_VERSION
except ImportError:
    SW_VERSION = "unknown"


utils_opts = [
    cfg.StrOpt('rootwrap_config',
               default="/etc/sysinv/rootwrap.conf",
               help='Path to the rootwrap configuration file to use for '
                    'running commands as root'),
    cfg.StrOpt('tempdir',
               default=None,
               help='Explicitly specify the temporary working directory'),
]

CONF = cfg.CONF
CONF.register_opts(utils_opts)

LOG = logging.getLogger(__name__)

# Used for looking up extensions of text
# to their 'multiplied' byte amount
BYTE_MULTIPLIERS = {
    '': 1,
    't': 1024 ** 4,
    'g': 1024 ** 3,
    'm': 1024 ** 2,
    'k': 1024,
}


class memoized(object):
    '''Decorator. Caches a function's return value each time it is called.
    If called later with the same arguments, the cached value is returned
    (not reevaluated).

    WARNING:  This function should not be used for class methods since it
    does not provide weak references; thus would prevent the instance from
    being garbage collected.
    '''
    def __init__(self, func):
        self.func = func
        self.cache = {}

    def __call__(self, *args):
        if not isinstance(args, collections.Hashable):
            # uncacheable. a list, for instance.
            # better to not cache than blow up.
            return self.func(*args)
        if args in self.cache:
            return self.cache[args]
        else:
            value = self.func(*args)
            self.cache[args] = value
            return value

    def __repr__(self):
        '''Return the function's docstring.'''
        return self.func.__doc__

    def __get__(self, obj, objtype):
        '''Support instance methods.'''
        return functools.partial(self.__call__, obj)


def _subprocess_setup():
    # Python installs a SIGPIPE handler by default. This is usually not what
    # non-Python subprocesses expect.
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)


def execute(*cmd, **kwargs):
    """Helper method to execute command with optional retry.

    If you add a run_as_root=True command, don't forget to add the
    corresponding filter to etc/sysinv/rootwrap.d !

    :param cmd:                Passed to subprocess.Popen.
    :param process_input:      Send to opened process.
    :param check_exit_code:    Single bool, int, or list of allowed exit
                               codes.  Defaults to [0].  Raise
                               exception.ProcessExecutionError unless
                               program exits with one of these code.
    :param delay_on_retry:     True | False. Defaults to True. If set to
                               True, wait a short amount of time
                               before retrying.
    :param attempts:           How many times to retry cmd.
    :param run_as_root:        True | False. Defaults to False. If set to True,
                               the command is run with rootwrap.

    :raises exception.SysinvException: on receiving unknown arguments
    :raises exception.ProcessExecutionError:

    :returns: a tuple, (stdout, stderr) from the spawned process, or None if
             the command fails.
    """
    process_input = kwargs.pop('process_input', None)
    check_exit_code = kwargs.pop('check_exit_code', [0])
    ignore_exit_code = False
    if isinstance(check_exit_code, bool):
        ignore_exit_code = not check_exit_code
        check_exit_code = [0]
    elif isinstance(check_exit_code, int):
        check_exit_code = [check_exit_code]
    delay_on_retry = kwargs.pop('delay_on_retry', True)
    attempts = kwargs.pop('attempts', 1)
    run_as_root = kwargs.pop('run_as_root', False)
    shell = kwargs.pop('shell', False)

    if len(kwargs):
        raise exception.SysinvException(_('Got unknown keyword args '
                                        'to utils.execute: %r') % kwargs)

    if run_as_root and os.geteuid() != 0:
        cmd = ['sudo', 'sysinv-rootwrap', CONF.rootwrap_config] + list(cmd)

    cmd = map(str, cmd)

    while attempts > 0:
        attempts -= 1
        try:
            LOG.debug(_('Running cmd (subprocess): %s'), ' '.join(cmd))
            _PIPE = subprocess.PIPE  # pylint: disable=E1101

            if os.name == 'nt':
                preexec_fn = None
                close_fds = False
            else:
                preexec_fn = _subprocess_setup
                close_fds = True

            obj = subprocess.Popen(cmd,
                                   stdin=_PIPE,
                                   stdout=_PIPE,
                                   stderr=_PIPE,
                                   close_fds=close_fds,
                                   preexec_fn=preexec_fn,
                                   shell=shell)
            result = None
            if process_input is not None:
                result = obj.communicate(process_input)
            else:
                result = obj.communicate()
            obj.stdin.close()  # pylint: disable=E1101
            _returncode = obj.returncode  # pylint: disable=E1101
            LOG.debug(_('Result was %s') % _returncode)
            if not ignore_exit_code and _returncode not in check_exit_code:
                (stdout, stderr) = result
                raise exception.ProcessExecutionError(
                        exit_code=_returncode,
                        stdout=stdout,
                        stderr=stderr,
                        cmd=' '.join(cmd))
            return result
        except exception.ProcessExecutionError:
            if not attempts:
                raise
            else:
                LOG.debug(_('%r failed. Retrying.'), cmd)
                if delay_on_retry:
                    greenthread.sleep(random.randint(20, 200) / 100.0)
        finally:
            # NOTE(termie): this appears to be necessary to let the subprocess
            #               call clean something up in between calls, without
            #               it two execute calls in a row hangs the second one
            greenthread.sleep(0)


def trycmd(*args, **kwargs):
    """A wrapper around execute() to more easily handle warnings and errors.

    Returns an (out, err) tuple of strings containing the output of
    the command's stdout and stderr.  If 'err' is not empty then the
    command can be considered to have failed.

    :discard_warnings   True | False. Defaults to False. If set to True,
                        then for succeeding commands, stderr is cleared

    """
    discard_warnings = kwargs.pop('discard_warnings', False)

    try:
        out, err = execute(*args, **kwargs)
        failed = False
    except exception.ProcessExecutionError as exn:
        out, err = '', str(exn)
        failed = True

    if not failed and discard_warnings and err:
        # Handle commands that output to stderr but otherwise succeed
        err = ''

    return out, err


# def ssh_connect(connection):
#    """Method to connect to a remote system using ssh protocol.
#
#    :param connection: a dict of connection parameters.
#    :returns: paramiko.SSHClient -- an active ssh connection.
#    :raises: SSHConnectFailed
#
#    """
#    try:
#        ssh = paramiko.SSHClient()
#        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
#        ssh.connect(connection.get('host'),
#                    username=connection.get('username'),
#                    password=connection.get('password', None),
#                    port=connection.get('port', 22),
#                    key_filename=connection.get('key_filename', None),
#                    timeout=connection.get('timeout', 10))
#
#        # send TCP keepalive packets every 20 seconds
#        ssh.get_transport().set_keepalive(20)
#    except Exception:
#        raise exception.SSHConnectFailed(host=connection.get('host'))
#
#    return ssh


def generate_uid(topic, size=8):
    characters = '01234567890abcdefghijklmnopqrstuvwxyz'
    choices = [random.choice(characters) for _x in range(size)]
    return '%s-%s' % (topic, ''.join(choices))


def random_alnum(size=32):
    characters = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    return ''.join(random.choice(characters) for _ in range(size))


class LazyPluggable(object):
    """A pluggable backend loaded lazily based on some value."""

    def __init__(self, pivot, config_group=None, **backends):
        self.__backends = backends
        self.__pivot = pivot
        self.__backend = None
        self.__config_group = config_group

    def __get_backend(self):
        if not self.__backend:
            if self.__config_group is None:
                backend_name = CONF[self.__pivot]
            else:
                backend_name = CONF[self.__config_group][self.__pivot]
            if backend_name not in self.__backends:
                msg = _('Invalid backend: %s') % backend_name
                raise exception.SysinvException(msg)

            backend = self.__backends[backend_name]
            if isinstance(backend, tuple):
                name = backend[0]
                fromlist = backend[1]
            else:
                name = backend
                fromlist = backend

            self.__backend = __import__(name, None, None, fromlist)
        return self.__backend

    def __getattr__(self, key):
        backend = self.__get_backend()
        return getattr(backend, key)


def delete_if_exists(pathname):
    """delete a file, but ignore file not found error."""

    try:
        os.unlink(pathname)
    except OSError as e:
        if e.errno == errno.ENOENT:
            return
        else:
            raise


def is_int_like(val):
    """Check if a value looks like an int."""
    try:
        return str(int(val)) == str(val)
    except Exception:
        return False


def is_float_like(val):
    """Check if a value looks like a float."""
    try:
        return str(float(val)) == str(val)
    except Exception:
        return False


def is_valid_boolstr(val):
    """Check if the provided string is a valid bool string or not."""
    boolstrs = ('true', 'false', 'yes', 'no', 'y', 'n', '1', '0')
    return str(val).lower() in boolstrs


def is_valid_mac(address):
    """Verify the format of a MAC address."""
    m = "[0-9a-f]{2}([-:])[0-9a-f]{2}(\\1[0-9a-f]{2}){4}$"
    if isinstance(address, six.string_types) and re.match(m, address.lower()):
        return True
    return False


def validate_and_normalize_mac(address):
    """Validate a MAC address and return normalized form.

    Checks whether the supplied MAC address is formally correct and
    normalize it to all lower case.

    :param address: MAC address to be validated and normalized.
    :returns: Normalized and validated MAC address.
    :raises: InvalidMAC If the MAC address is not valid.
    :raises: ClonedInterfaceNotFound If MAC address is not updated
             while installing a cloned image.

    """
    if not is_valid_mac(address):
        if constants.CLONE_ISO_MAC in address:
            # get interface name from the label
            intf_name = address.rsplit('-', 1)[1][1:]
            raise exception.ClonedInterfaceNotFound(intf=intf_name)
        else:
            raise exception.InvalidMAC(mac=address)
    return address.lower()


def is_valid_ipv4(address):
    """Verify that address represents a valid IPv4 address."""
    try:
        return netaddr.valid_ipv4(address)
    except Exception:
        return False


def is_valid_ipv6(address):
    try:
        return netaddr.valid_ipv6(address)
    except Exception:
        return False


def is_valid_ip(address):
    if not is_valid_ipv4(address):
        return is_valid_ipv6(address)
    return True


def is_valid_ipv6_cidr(address):
    try:
        str(netaddr.IPNetwork(address, version=6).cidr)
        return True
    except Exception:
        return False


def get_shortened_ipv6(address):
    addr = netaddr.IPAddress(address, version=6)
    return str(addr.ipv6())


def get_shortened_ipv6_cidr(address):
    net = netaddr.IPNetwork(address, version=6)
    return str(net.cidr)


def is_valid_cidr(address):
    """Check if the provided ipv4 or ipv6 address is a valid CIDR address."""
    try:
        # Validate the correct CIDR Address
        netaddr.IPNetwork(address)
    except netaddr.core.AddrFormatError:
        return False
    except UnboundLocalError:
        # NOTE(MotoKen): work around bug in netaddr 0.7.5 (see detail in
        # https://github.com/drkjam/netaddr/issues/2)
        return False

    # Prior validation partially verify /xx part
    # Verify it here
    ip_segment = address.split('/')

    if (len(ip_segment) <= 1 or ip_segment[1] == ''):
        return False

    return True


def is_valid_hex(num):
    try:
        int(num, 16)
    except ValueError:
        return False
    return True


def is_valid_pci_device_vendor_id(id):
    """Check if the provided id is a valid 16 bit hexadecimal."""
    val = id.replace('0x', '').strip()
    if not is_valid_hex(id):
        return False
    if (len(val) > 4):
        return False
    return True


def is_valid_pci_class_id(id):
    """Check if the provided id is a valid 16 bit hexadecimal."""
    val = id.replace('0x', '').strip()
    if not is_valid_hex(id):
        return False
    if (len(val) > 6):
        return False
    return True


def is_system_usable_block_device(pydev_device):
    """ Check if a block device is local and can be used for partitioning

    Example devices:
     o local block devices: local HDDs, SSDs, RAID arrays
     o remote devices: iscsi mounted, LIO, EMC
     o non permanent devices: USB stick
    :return bool: True if device can be used else False
    """
    if pydev_device.get("ID_BUS") == "usb":
        # Skip USB devices
        return False
    if pydev_device.get("DM_VG_NAME") or pydev_device.get("DM_LV_NAME"):
        # Skip LVM devices
        return False
    id_path = pydev_device.get("ID_PATH", "")
    if "iqn." in id_path or "eui." in id_path:
        # Skip all iSCSI devices, they are links for volume storage.
        # As per https://www.ietf.org/rfc/rfc3721.txt, "iqn." or "edu."
        # have to be present when constructing iSCSI names.
        return False
    if pydev_device.get("ID_VENDOR") == constants.VENDOR_ID_LIO:
        # LIO devices are iSCSI, should be skipped above!
        LOG.error("Invalid id_path. Device %s (%s) is iSCSI!" %
                    (id_path, pydev_device.get('DEVNAME')))
        return False
    return True


def get_ip_version(network):
    """Returns the IP version of a network (IPv4 or IPv6).

    :raises: AddrFormatError if invalid network.
    """
    if netaddr.IPNetwork(network).version == 6:
        return "IPv6"
    elif netaddr.IPNetwork(network).version == 4:
        return "IPv4"


def convert_to_list_dict(lst, label):
    """Convert a value or list into a list of dicts."""
    if not lst:
        return None
    if not isinstance(lst, list):
        lst = [lst]
    return [{label: x} for x in lst]


def sanitize_hostname(hostname):
    """Return a hostname which conforms to RFC-952 and RFC-1123 specs."""
    if isinstance(hostname, six.string_types):
        hostname = hostname.encode('latin-1', 'ignore')

    hostname = re.sub('[ _]', '-', hostname)
    hostname = re.sub('[^\w.-]+', '', hostname)
    hostname = hostname.lower()
    hostname = hostname.strip('.-')

    return hostname


def read_cached_file(filename, cache_info, reload_func=None):
    """Read from a file if it has been modified.

    :param cache_info: dictionary to hold opaque cache.
    :param reload_func: optional function to be called with data when
                        file is reloaded due to a modification.

    :returns: data from file

    """
    mtime = os.path.getmtime(filename)
    if not cache_info or mtime != cache_info.get('mtime'):
        LOG.debug(_("Reloading cached file %s") % filename)
        with open(filename) as fap:
            cache_info['data'] = fap.read()
        cache_info['mtime'] = mtime
        if reload_func:
            reload_func(cache_info['data'])
    return cache_info['data']


def file_open(*args, **kwargs):
    """Open file

    see built-in file() documentation for more details

    Note: The reason this is kept in a separate module is to easily
          be able to provide a stub module that doesn't alter system
          state at all (for unit tests)
    """
    return file(*args, **kwargs)


def hash_file(file_like_object):
    """Generate a hash for the contents of a file."""
    checksum = hashlib.sha1()
    for chunk in iter(lambda: file_like_object.read(32768), b''):
        checksum.update(chunk)
    return checksum.hexdigest()


@contextlib.contextmanager
def temporary_mutation(obj, **kwargs):
    """Temporarily set the attr on a particular object to a given value then
    revert when finished.

    One use of this is to temporarily set the read_deleted flag on a context
    object:

        with temporary_mutation(context, read_deleted="yes"):
            do_something_that_needed_deleted_objects()
    """
    def is_dict_like(thing):
        return isinstance(thing,dict)

    def get(thing, attr, default):
        if is_dict_like(thing):
            return thing.get(attr, default)
        else:
            return getattr(thing, attr, default)

    def set_value(thing, attr, val):
        if is_dict_like(thing):
            thing[attr] = val
        else:
            setattr(thing, attr, val)

    def delete(thing, attr):
        if is_dict_like(thing):
            del thing[attr]
        else:
            delattr(thing, attr)

    NOT_PRESENT = object()

    old_values = {}
    for attr, new_value in kwargs.items():
        old_values[attr] = get(obj, attr, NOT_PRESENT)
        set_value(obj, attr, new_value)

    try:
        yield
    finally:
        for attr, old_value in old_values.items():
            if old_value is NOT_PRESENT:
                delete(obj, attr)
            else:
                set_value(obj, attr, old_value)


@contextlib.contextmanager
def tempdir(**kwargs):
    tempfile.tempdir = CONF.tempdir
    tmpdir = tempfile.mkdtemp(**kwargs)
    try:
        yield tmpdir
    finally:
        try:
            shutil.rmtree(tmpdir)
        except OSError as e:
            LOG.error(_('Could not remove tmpdir: %s'), str(e))


def mkfs(fs, path, label=None):
    """Format a file or block device

    :param fs: Filesystem type (examples include 'swap', 'ext3', 'ext4'
               'btrfs', etc.)
    :param path: Path to file or block device to format
    :param label: Volume label to use
    """
    if fs == 'swap':
        args = ['mkswap']
    else:
        args = ['mkfs', '-t', fs]
    # add -F to force no interactive execute on non-block device.
    if fs in ('ext3', 'ext4'):
        args.extend(['-F'])
    if label:
        if fs in ('msdos', 'vfat'):
            label_opt = '-n'
        else:
            label_opt = '-L'
        args.extend([label_opt, label])
    args.append(path)
    execute(*args)


# TODO(deva): Make these work in Sysinv.
#             Either copy nova/virt/utils (bad),
#             or reimplement as a common lib,
#             or make a driver that doesn't need to do this.
#
# def cache_image(context, target, image_id, user_id, project_id):
#     if not os.path.exists(target):
#         libvirt_utils.fetch_image(context, target, image_id,
#                                   user_id, project_id)
#
#
# def inject_into_image(image, key, net, metadata, admin_password,
#         files, partition, use_cow=False):
#     try:
#         disk_api.inject_data(image, key, net, metadata, admin_password,
#                 files, partition, use_cow)
#     except Exception as e:
#         LOG.warn(_("Failed to inject data into image %(image)s. "
#                    "Error: %(e)s") % locals())


def unlink_without_raise(path):
    try:
        os.unlink(path)
    except OSError as e:
        if e.errno == errno.ENOENT:
            return
        else:
            LOG.warn(_("Failed to unlink %(path)s, error: %(e)s") %
                      {'path': path, 'e': e})


def rmtree_without_raise(path):
    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
    except OSError as e:
        LOG.warn(_("Failed to remove dir %(path)s, error: %(e)s") %
                {'path': path, 'e': e})


def write_to_file(path, contents):
    with open(path, 'w') as f:
        f.write(contents)


def create_link_without_raise(source, link):
    try:
        os.symlink(source, link)
    except OSError as e:
        if e.errno == errno.EEXIST:
            return
        else:
            LOG.warn(_("Failed to create symlink from %(source)s to %(link)s"
                       ", error: %(e)s") %
                       {'source': source, 'link': link, 'e': e})


def safe_rstrip(value, chars=None):
    """Removes trailing characters from a string if that does not make it empty

    :param value: A string value that will be stripped.
    :param chars: Characters to remove.
    :return: Stripped value.

    """
    if not isinstance(value, six.string_types):
        LOG.warn(_("Failed to remove trailing character. Returning original "
                   "object. Supplied object is not a string: %s,") % value)
        return value

    return value.rstrip(chars) or value


def generate_uuid():
    return str(uuid.uuid4())


def is_uuid_like(val):
    """Returns validation of a value as a UUID.

    For our purposes, a UUID is a canonical form string:
    aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa

    """
    try:
        return str(uuid.UUID(val)) == val
    except (TypeError, ValueError, AttributeError):
        return False


def removekey(d, key):
    r = dict(d)
    del r[key]
    return r


def removekeys_nonmtce(d, keepkeys=None):
    if not keepkeys:
        keepkeys = []

    nonmtce_keys = ['created_at',
                    'updated_at',
                    'ihost_action',
                    'action_state',
                    'vim_progress_status',
                    'task',
                    'uptime',
                    'location',
                    'serialid',
                    'config_status',
                    'config_applied',
                    'config_target',
                    'reserved',
                    'forisystemid']
    r = dict(d)

    for k in nonmtce_keys:
        if r.get(k) and (k not in keepkeys):
            del r[k]
    return r


def removekeys_nonhwmon(d, keepkeys=None):
    if not keepkeys:
        keepkeys = []

    nonmtce_keys = ['created_at',
                    'updated_at',
                    ]
    r = dict(d)

    for k in nonmtce_keys:
        if r.get(k) and (k not in keepkeys):
            del r[k]
    return r


def notify_mtc_and_recv(mtc_address, mtc_port, idict):
    mtc_response_dict = {}
    mtc_response_dict['status'] = None

    serialized_idict = json.dumps(idict)

    # notify mtc this ihost has been added
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.setblocking(1)  # blocking, timeout must be specified
        s.settimeout(6)   # give mtc a few secs to respond
        s.connect((mtc_address, mtc_port))
        LOG.warning("Mtc Command : %s" % serialized_idict)
        s.sendall(serialized_idict)

        mtc_response = s.recv(1024)  # check if mtc allows
        try:
            mtc_response_dict = json.loads(mtc_response)
            LOG.warning("Mtc Response: %s" % mtc_response_dict)
        except Exception:
            LOG.exception("Mtc Response Error: %s" % mtc_response)
            pass

    except socket.error, e:
        LOG.exception(_("Socket Error: %s on %s:%s for %s") % (e,
                        mtc_address, mtc_port, serialized_idict))
        # if e not in [errno.EWOULDBLOCK, errno.EINTR]:
        #  raise exception.CommunicationError(_(
        #   "Socket error:  address=%s port=%s error=%s ") % (
        #    self._mtc_address, self._mtc_port, e))
        pass

    finally:
        s.close()

    return mtc_response_dict


def touch(fname):
    with open(fname, 'a'):
        os.utime(fname, None)


def symlink_force(source, link_name):
    """ Force creation of a symlink
        Params:
            source: path to the source
            link_name: symbolic link name
    """
    try:
        os.symlink(source, link_name)
    except OSError, e:
        if e.errno == errno.EEXIST:
            os.remove(link_name)
            os.symlink(source, link_name)


@contextlib.contextmanager
def mounted(remote_dir, local_dir):
    local_dir = os.path.abspath(local_dir)
    try:
        subprocess.check_output(
            ["/bin/nfs-mount", remote_dir, local_dir],
            stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        raise OSError(("mount operation failed: "
                       "command={}, retcode={}, output='{}'").format(
                          e.cmd, e.returncode, e.output))
    try:
        yield
    finally:
        try:
            subprocess.check_output(
                ["/bin/umount", local_dir],
                stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            raise OSError(("umount operation failed: "
                           "command={}, retcode={}, output='{}'").format(
                              e.cmd, e.returncode, e.output))


def timestamped(dname, fmt='{dname}_%Y-%m-%d-%H-%M-%S'):
    return datetime.datetime.now().strftime(fmt).format(dname=dname)


def nested_object(objclass, none_ok=True):
    def validator(val, objclass=objclass):
        if none_ok and val is None:
            return val
        if isinstance(val, objclass):
            return val
        raise ValueError('An object of class %s is required here' % objclass)
    return validator


def host_has_function(iHost, function):
    return function in (iHost.get('subfunctions') or iHost['personality'] or '')


@memoized
def is_virtual():
    '''
    Determines if the system is virtualized or not
    '''
    subp = subprocess.Popen(['facter', 'is_virtual'],
                            stdout=subprocess.PIPE)
    if subp.wait():
        raise Exception("Failed to read virtualization status from facter")
    output = subp.stdout.readlines()
    if len(output) != 1:
        raise Exception("Unexpected number of lines: %d" % len(output))
    result = output[0].strip()
    return bool(result == 'true')


def is_virtual_compute(ihost):
    if not(os.path.isdir("/etc/sysinv/.virtual_compute_nodes")):
        return False
    try:
        ip = ihost['mgmt_ip']
        return os.path.isfile("/etc/sysinv/.virtual_compute_nodes/%s" % ip)
    except AttributeError:
        return False


def is_low_core_system(ihost, dba):
    """
    Determine if the hosts core count is less than or equal to a xeon-d cpu
    used with get_required_platform_reserved_memory to set the required
    platform memory for xeon-d systems
    """
    cpu_list = dba.icpu_get_by_ihost(ihost['uuid'])
    number_physical_cores = 0
    for cpu in cpu_list:
        if int(cpu['thread']) == 0:
            number_physical_cores += 1
    return number_physical_cores <= constants.NUMBER_CORES_XEOND


def get_minimum_platform_reserved_memory(ihost, numa_node):
    """Returns the minimum amount of memory to be reserved by the platform for a
        given NUMA node.  Compute nodes require reserved memory because the
        balance of the memory is allocated to VM instances.  Other node types
        have exclusive use of the memory so no explicit reservation is
        required. Memory required by platform core is not included here.
        """
    reserved = 0
    if numa_node is None:
        return reserved
    if is_virtual() or is_virtual_compute(ihost):
        # minimal memory requirements for VirtualBox
        if host_has_function(ihost, constants.COMPUTE):
            if numa_node == 0:
                reserved += 1200
                if host_has_function(ihost, constants.CONTROLLER):
                    reserved += 5000
            else:
                reserved += 500
    else:
        if host_has_function(ihost, constants.COMPUTE):
            # Engineer 2G per numa node for disk IO RSS overhead
            reserved += constants.DISK_IO_RESIDENT_SET_SIZE_MIB
    return reserved


def get_required_platform_reserved_memory(ihost, numa_node, low_core=False):
    """Returns the amount of memory to be reserved by the platform for a
    given NUMA node.  Compute nodes require reserved memory because the
    balance of the memory is allocated to VM instances.  Other node types
    have exclusive use of the memory so no explicit reservation is
    required.
    """
    required_reserved = 0
    if numa_node is None:
        return required_reserved
    if is_virtual() or is_virtual_compute(ihost):
        # minimal memory requirements for VirtualBox
        required_reserved += constants.DISK_IO_RESIDENT_SET_SIZE_MIB_VBOX
        if host_has_function(ihost, constants.COMPUTE):
            if numa_node == 0:
                required_reserved += \
                    constants.PLATFORM_CORE_MEMORY_RESERVED_MIB_VBOX
                if host_has_function(ihost, constants.CONTROLLER):
                    required_reserved += \
                        constants.COMBINED_NODE_CONTROLLER_MEMORY_RESERVED_MIB_VBOX
                else:
                    # If not a controller, add overhead for metadata and vrouters
                    required_reserved += \
                        constants.NETWORK_METADATA_OVERHEAD_MIB_VBOX
            else:
                required_reserved += \
                    constants.DISK_IO_RESIDENT_SET_SIZE_MIB_VBOX
    else:
        if host_has_function(ihost, constants.COMPUTE):
            # Engineer 2G per numa node for disk IO RSS overhead
            required_reserved += constants.DISK_IO_RESIDENT_SET_SIZE_MIB
            if numa_node == 0:
                # Engineer 2G for compute to give some headroom;
                # typically requires 650 MB PSS
                required_reserved += \
                    constants.PLATFORM_CORE_MEMORY_RESERVED_MIB
                if host_has_function(ihost, constants.CONTROLLER):
                    # Over-engineer controller memory.
                    # Typically require 5GB PSS; accommodate 2GB headroom.
                    # Controller memory usage depends on number of workers.
                    if low_core:
                        required_reserved += \
                            constants.COMBINED_NODE_CONTROLLER_MEMORY_RESERVED_MIB_XEOND
                    else:
                        required_reserved += \
                            constants.COMBINED_NODE_CONTROLLER_MEMORY_RESERVED_MIB
                else:
                    # If not a controller,
                    # add overhead for metadata and vrouters
                    required_reserved += \
                        constants.NETWORK_METADATA_OVERHEAD_MIB
    return required_reserved


def get_network_type_list(interface):
    if interface['networktype']:
        return [n.strip() for n in interface['networktype'].split(",")]
    else:
        return []


def is_pci_network_types(networktypelist):
    """
    Check if the network type consists of the combined PCI passthrough
    and SRIOV network types.
    """
    return (len(constants.PCI_NETWORK_TYPES) == len(networktypelist) and
            all(i in networktypelist for i in constants.PCI_NETWORK_TYPES))


def get_primary_network_type(interface):
    """
    An interface can be associated with up to 2 network types but it can only
    have 1 primary network type.  The additional network type can only be
    'data' and is used as a placeholder to indicate that there is at least one
    VLAN based neutron provider network associated to the interface.  This
    information is used to determine whether the vswitch on the compute needs
    to control the interface or not.   This function examines the list of
    network types, discards the secondary type (if any) and returns the primary
    network type.
    """
    if not interface['ifclass'] or interface['ifclass'] == constants.INTERFACE_CLASS_NONE:
        return None
    primary_network_type = None
    if interface['ifclass'] == constants.INTERFACE_CLASS_DATA:
        primary_network_type = constants.NETWORK_TYPE_DATA
    elif interface['ifclass'] == constants.INTERFACE_CLASS_PCI_PASSTHROUGH:
        primary_network_type = constants.NETWORK_TYPE_PCI_PASSTHROUGH
    elif interface['ifclass'] == constants.INTERFACE_CLASS_PCI_SRIOV:
        primary_network_type = constants.NETWORK_TYPE_PCI_SRIOV
    elif interface['ifclass'] == constants.INTERFACE_CLASS_PLATFORM:
        if not interface['networktype'] or interface[
                'networktype'] == constants.NETWORK_TYPE_NONE:
            return None
        primary_network_type = interface['networktype']

    return primary_network_type


def get_sw_version():
    return SW_VERSION


class ISO(object):

    def __init__(self, iso_path, mount_dir):
        self.iso_path = iso_path
        self.mount_dir = mount_dir
        self._iso_mounted = False
        self._mount_iso()

    def __del__(self):
        if self._iso_mounted:
            self._umount_iso()

    def _mount_iso(self):
        with open(os.devnull, "w") as fnull:
            subprocess.check_call(['mkdir', '-p', self.mount_dir], stdout=fnull,
                                  stderr=fnull)
            subprocess.check_call(['mount', '-r', '-o', 'loop', self.iso_path,
                                   self.mount_dir],
                                  stdout=fnull,
                                  stderr=fnull)
        self._iso_mounted = True

    def _umount_iso(self):
        try:
            # Do a lazy unmount to handle cases where a file in the mounted
            # directory is open when the umount is done.
            subprocess.check_call(['umount', '-l', self.mount_dir])
            self._iso_mounted = False
        except subprocess.CalledProcessError as e:
            # If this fails for some reason, there's not a lot we can do
            # Just log the exception and keep going
            LOG.exception(e)


def get_active_load(loads):
    active_load = None
    for db_load in loads:
        if db_load.state == constants.ACTIVE_LOAD_STATE:
            active_load = db_load

    if active_load is None:
        raise exception.SysinvException(_("No active load found"))

    return active_load


def get_imported_load(loads):
    imported_load = None
    for db_load in loads:
        if db_load.state == constants.IMPORTED_LOAD_STATE:
            imported_load = db_load

    if imported_load is None:
        raise exception.SysinvException(_("No imported load found"))

    return imported_load


def validate_loads_for_import(loads):
    for db_load in loads:
        if db_load.state == constants.IMPORTED_LOAD_STATE:
            raise exception.SysinvException(_("Imported load exists."))


def validate_load_for_delete(load):
    if not load:
        raise exception.SysinvException(_("Load not found"))

    valid_delete_states = [
        constants.IMPORTED_LOAD_STATE,
        constants.ERROR_LOAD_STATE,
        constants.DELETING_LOAD_STATE
    ]

    if load.state not in valid_delete_states:
        raise exception.SysinvException(
            _("Only a load in an imported or error state can be deleted"))


def gethostbyname(hostname):
    return socket.getaddrinfo(hostname, None)[0][4][0]


def get_local_controller_hostname():
    try:
        local_hostname = socket.gethostname()
    except Exception as e:
        raise exception.SysinvException(_(
            "Failed to get the local hostname: %s") % str(e))
    return local_hostname


def get_mate_controller_hostname(hostname=None):
    if not hostname:
        try:
            hostname = socket.gethostname()
        except Exception as e:
            raise exception.SysinvException(_(
                "Failed to get the local hostname: %s") % str(e))

    if hostname == constants.CONTROLLER_0_HOSTNAME:
        mate_hostname = constants.CONTROLLER_1_HOSTNAME
    elif hostname == constants.CONTROLLER_1_HOSTNAME:
        mate_hostname = constants.CONTROLLER_0_HOSTNAME
    else:
        raise exception.SysinvException(_(
            "Unknown local hostname: %s)" % hostname))

    return mate_hostname


def format_address_name(hostname, network_type):
    return "%s-%s" % (hostname, network_type)


def validate_yes_no(name, value):
    if value.lower() not in ['y', 'n']:
        raise wsme.exc.ClientSideError((
            "Parameter '%s' must be a y/n value." % name))


def get_interface_os_ifname(interface, interfaces, ports):
    """
    Returns the operating system name for an interface.  The user is allowed to
    override the sysinv DB interface name for convenience, but that name is not
    used at the operating system level for all interface types.  For ethernet
    and VLAN interfaces the name follows the native interface names while for
    AE interfaces the user defined name is used.
    """
    if interface['iftype'] == constants.INTERFACE_TYPE_VLAN:
        # VLAN interface names are built-in using the o/s name of the lower
        # interface object.
        lower_iface = interfaces[interface['uses'][0]]
        lower_ifname = get_interface_os_ifname(lower_iface, interfaces, ports)
        return '{}.{}'.format(lower_ifname, interface['vlan_id'])
    elif interface['iftype'] == constants.INTERFACE_TYPE_ETHERNET:
        # Ethernet interface names are always based on the port name which is
        # just the normal o/s name of the original network interface
        lower_ifname = ports[interface['id']]['name']
        return lower_ifname
    else:
        # All other interfaces default to the user-defined name
        return interface['ifname']


def get_dhcp_cid(hostname, network_type, mac):
    """Create the CID for use with dnsmasq. We use a unique identifier for a
    client since different networks can operate over the same device (and hence
    same MAC addr) when VLAN interfaces are concerned.  The format is different
    based on network type because the mgmt network uses a default because it
    needs to exist before the board is handled by sysinv (i.e., the CID needs
    to exist in the dhclient.conf file at build time) while the infra network
    is built dynamically to avoid colliding with the mgmt CID.

    Example:
    Format = 'id:' + colon-separated-hex(hostname:network_type) + ":" + mac
    """
    if network_type == constants.NETWORK_TYPE_INFRA:
        prefix = '{}:{}'.format(hostname, network_type)
        prefix = ':'.join(x.encode('hex') for x in prefix)
    elif network_type == constants.NETWORK_TYPE_MGMT:
        # Our default dhclient.conf files requests a prefix of '00:03:00' to
        # which dhclient adds a hardware address type of 01 to make final
        # prefix of '00:03:00:01'.
        prefix = '00:03:00:01'
    else:
        raise Exception("Network type {} does not support DHCP".format(
            network_type))
    return '{}:{}'.format(prefix, mac)


def get_personalities(host_obj):
    """
        Determine the personalities from host_obj
    """
    personalities = host_obj.subfunctions.split(',')
    if constants.LOWLATENCY in personalities:
        personalities.remove(constants.LOWLATENCY)
    return personalities


def is_cpe(host_obj):
    return (host_has_function(host_obj, constants.CONTROLLER) and
            host_has_function(host_obj, constants.COMPUTE))


def output_to_dict(output):
    dict = {}
    output = filter(None, output.split('\n'))

    for row in output:
        values = row.split()
        if len(values) != 2:
            raise Exception("The following output does not respect the "
                            "format: %s" % row)
        dict[values[1]] = values[0]

    return dict


def bytes_to_GiB(bytes_number):
    return bytes_number / float(1024 ** 3)


def bytes_to_MiB(bytes_number):
    return bytes_number / float(1024 ** 2)


def check_lock_path():
    if os.path.isdir(constants.SYSINV_LOCK_PATH):
        return
    try:
        uid = pwd.getpwnam(constants.SYSINV_USERNAME).pw_uid
        gid = grp.getgrnam(constants.SYSINV_GRPNAME).gr_gid
        os.makedirs(constants.SYSINV_LOCK_PATH)
        os.chown(constants.SYSINV_LOCK_PATH, uid, gid)
        LOG.info("Created directory=%s" %
                 constants.SYSINV_LOCK_PATH)

    except OSError as e:
        LOG.exception("makedir %s OSError=%s encountered" %
                      (constants.SYSINV_LOCK_PATH, e))


def synchronized(name, external=True):
    if external:
        check_lock_path()
        lock_path = constants.SYSINV_LOCK_PATH
    else:
        lock_path = None
    return lockutils.synchronized(name,
                                  lock_file_prefix='sysinv-',
                                  external=external,
                                  lock_path=lock_path)


# TODO (rchurch): refactor this. Need for upgrades? Combine needs with
# _get_cinder_device_info()
def _get_cinder_device(dbapi, forihostid):
    if not forihostid:
        LOG.error("_get_cinder_device: host not defined. ")
        return

    cinder_device = None

    i_stors = dbapi.istor_get_by_ihost(forihostid)
    for stor in i_stors:
        if stor.function == constants.STOR_FUNCTION_CINDER:
            # Obtain the cinder disk.
            cinder_disk_uuid = stor.idisk_uuid
            cinder_disk = dbapi.idisk_get(cinder_disk_uuid)
            # Obtain the cinder device as the disk's device path.
            if cinder_disk.device_path:
                cinder_device = cinder_disk.device_path
            elif cinder_disk.device_node:
                # During upgrade from 16.10, the cinder device_path may
                # not be set for controller-0
                cinder_device = cinder_disk.device_node
                LOG.info("JKUNG host %s cinder device_path does not exist, return "
                         "device_node=%s" % (forihostid, cinder_disk.device_node))

    return cinder_device


def _get_cinder_device_info(dbapi, forihostid):
    if not forihostid:
        LOG.error("_get_cinder_device: host not defined. ")
        return

    cinder_device = None
    cinder_size_gib = 0

    # TODO (rchurch): get a DB query based on volume group name
    lvgs = dbapi.ilvg_get_by_ihost(forihostid)
    for vg in lvgs:
        if vg.lvm_vg_name == constants.LVG_CINDER_VOLUMES:
            pvs = dbapi.ipv_get_by_ihost(forihostid)
            for pv in pvs:
                if pv.forilvgid == vg.id:
                    # NOTE: Only supporting a single PV for cinder volumes
                    if cinder_device:
                        LOG.error("Another cinder device? ignoring! pv: %s" % pv.uuid)
                        continue
                    cinder_device = pv.disk_or_part_device_path

                    # NOTE: Should only ever be a single partition until we support
                    #       multiple PVs for cinder. Cinder device should
                    #       not be a disk. Log an error and continue
                    # Get the size of the pv from the parition info
                    try:
                        part = dbapi.partition_get(pv.disk_or_part_uuid)
                        cinder_size_gib = (int)(part.size_mib) >> 1
                    except exception.DiskPartitionNotFound:
                        LOG.error("Discovered cinder device is not a partition.")

    return cinder_device, cinder_size_gib


def skip_udev_partition_probe(function):
    def wrapper(*args, **kwargs):
        """Decorator to skip partition rescanning in udev

        When reading partitions we have to avoid rescanning them as this
        will temporarily delete their dev nodes causing devastating effects
        for commands that rely on them (e.g. ceph-disk).

        UDEV triggers a partition rescan when a device node opened in write
        mode is closed. To avoid this, we have to acquire a shared lock on the
        device before other close operations do.

        Since both parted and sgdisk always open block devices in RW mode we
        must disable udev from triggering the rescan when we just need to get
        partition information.

        This happens due to a change in udev v214. For details see:
            http://tracker.ceph.com/issues/14080
            http://tracker.ceph.com/issues/15176
            https://github.com/systemd/systemd/commit/02ba8fb3357daf57f6120ac512fb464a4c623419

        :param   device_node: dev node or path of the device
        :returns decorated function
        """
        device_node = kwargs.get('device_node', None)
        if device_node:
            with open(device_node, 'r') as f:
                fcntl.flock(f, fcntl.LOCK_SH | fcntl.LOCK_NB)
                try:
                    return function(*args, **kwargs)
                finally:
                    # Since events are asynchronous we have to wait for udev
                    # to pick up the change.
                    time.sleep(0.1)
                    fcntl.flock(f, fcntl.LOCK_UN)
        else:
            return function(*args, **kwargs)
    return wrapper


def disk_is_gpt(device_node):
    """Checks if a device node is of GPT format.
    :param   device_node: the disk's device node
    :returns: True if partition table on disk is GPT
              False if partition table on disk is not GPT
    """
    parted_command = '{} {} {}'.format('parted -s', device_node, 'print')
    parted_process = subprocess.Popen(
        parted_command, stdout=subprocess.PIPE, shell=True)
    parted_output = parted_process.stdout.read()
    if re.search('Partition Table: gpt', parted_output):
        return True

    return False


def partitions_are_in_order(disk_partitions, requested_partitions):
    """Determine if a list of requested partitions can be created on a disk
    with other existing partitions."""

    partitions_nr = []

    for dp in disk_partitions:
        part_number = re.match('.*?([0-9]+)$', dp.get('device_path')).group(1)
        partitions_nr.append(int(part_number))

    for rp in requested_partitions:
        part_number = re.match('.*?([0-9]+)$', rp.get('device_path')).group(1)
        partitions_nr.append(int(part_number))

    return sorted(partitions_nr) == range(min(partitions_nr),
                                          max(partitions_nr) + 1)


# TODO(oponcea): Remove once sm supports in-service configuration reload.
def is_single_controller(dbapi):
    # Check the number of provisioned/provisioning hosts. If there is
    # only one then we have a single controller (AIO-SX, single AIO-DX, or
    # single std controller). If this is the case reset sm after adding
    # cinder so that cinder DRBD/processes are managed.
    hosts = dbapi.ihost_get_list()
    prov_hosts = [h for h in hosts
                  if h.invprovision in [constants.PROVISIONED,
                                        constants.PROVISIONING]]
    if len(prov_hosts) == 1:
        return True
    return False


def is_partition_the_last(dbapi, partition):
    """Check that the partition we are trying to delete is the last partition
       on disk.
    """
    idisk_uuid = partition.get('idisk_uuid')
    onidisk_parts = dbapi.partition_get_by_idisk(idisk_uuid)
    part_number = re.match('.*?([0-9]+)$',
                           partition.get('device_path')).group(1)

    if int(part_number) != len(onidisk_parts):
        return False

    return True


def perform_distributed_cloud_config(dbapi, mgmt_iface_id):
    """
    Check if we are running in distributed cloud mode and perform any
    necessary configuration.
    """

    system = dbapi.isystem_get_one()
    if system.distributed_cloud_role == \
            constants.DISTRIBUTED_CLOUD_ROLE_SYSTEMCONTROLLER:
        # Add routes to get from this controller to all the existing subclouds.
        # Do this by copying all the routes configured on the management
        # interface on the mate controller (if it exists).
        mgmt_iface = dbapi.iinterface_get(mgmt_iface_id)
        controller_hosts = dbapi.ihost_get_by_personality(constants.CONTROLLER)
        mate_controller_id = None
        for controller in controller_hosts:
            if controller.id != mgmt_iface.forihostid:
                # Found the mate controller
                mate_controller_id = controller.id
                break
        else:
            LOG.info("Mate controller for host id %d not found. Routes not "
                     "added." % mgmt_iface.forihostid)
            return

        mate_interfaces = dbapi.iinterface_get_all(
            forihostid=mate_controller_id)
        for interface in mate_interfaces:
            if interface.networktype == constants.NETWORK_TYPE_MGMT:
                mate_mgmt_iface = interface
                break
        else:
            LOG.error("Management interface for host id %d not found." %
                      mate_controller_id)
            return

        routes = dbapi.routes_get_by_interface(mate_mgmt_iface.id)
        for route in routes:
            new_route = {
                'family': route.family,
                'network': route.network,
                'prefix': route.prefix,
                'gateway': route.gateway,
                'metric': route.metric
            }
            try:
                dbapi.route_create(mgmt_iface_id, new_route)
            except exception.RouteAlreadyExists:
                LOG.info("DC Config: Attempting to add duplicate route "
                         "to system controller.")
                pass

            LOG.info("DC Config: Added route to subcloud: "
                     "%s/%s gw:%s on mgmt_iface_id: %s" %
                     (new_route['network'], new_route['prefix'],
                      new_route['gateway'], mgmt_iface_id))

    elif system.distributed_cloud_role == \
            constants.DISTRIBUTED_CLOUD_ROLE_SUBCLOUD:
        # Add the route back to the system controller.
        # Assumption is we do not have to do any error checking
        # for local & reachable gateway etc, as config_subcloud
        # will have already done these checks before allowing
        # the system controller gateway into the database.

        cc_gtwy_addr_name = '%s-%s' % (
            constants.SYSTEM_CONTROLLER_GATEWAY_IP_NAME,
            constants.NETWORK_TYPE_MGMT)

        try:
            cc_gtwy_addr = dbapi.address_get_by_name(
                cc_gtwy_addr_name)
        except exception.AddressNotFoundByName:
            LOG.warning("DC Config: Failed to retrieve central "
                        "cloud gateway ip address")
            return

        try:
            cc_network = dbapi.network_get_by_type(
                constants.NETWORK_TYPE_SYSTEM_CONTROLLER)
        except exception.NetworkTypeNotFound:
            LOG.warning("DC Config: Failed to retrieve central "
                        "cloud network")
            return

        cc_network_addr_pool = dbapi.address_pool_get(
            cc_network.pool_uuid)

        route = {
            'family': cc_network_addr_pool.family,
            'network': cc_network_addr_pool.network,
            'prefix': cc_network_addr_pool.prefix,
            'gateway': cc_gtwy_addr.address,
            'metric': 1
        }

        try:
            dbapi.route_create(mgmt_iface_id, route)
        except exception.RouteAlreadyExists:
            LOG.info("DC Config: Attempting to add duplicate route "
                     "to system controller.")
            pass

        LOG.info("DC Config: Added route to system "
                 "controller: %s/%s gw:%s on mgmt_iface_id: %s" %
                 (cc_network_addr_pool.network, cc_network_addr_pool.prefix,
                  cc_gtwy_addr.address, mgmt_iface_id))


def _check_upgrade(dbapi, host_obj=None):
    """ Check whether partition operation may be allowed.

        If there is an upgrade in place, reject the operation if the
        host was not created after upgrade start.
    """
    try:
        upgrade = dbapi.software_upgrade_get_one()
    except exception.NotFound:
        return

    if host_obj:
        if host_obj.created_at > upgrade.created_at:
            LOG.info("New host %s created after upgrade, allow partition" %
                     host_obj.hostname)
            return

    raise wsme.exc.ClientSideError(
        _("ERROR: Disk partition operations are not allowed during a "
          "software upgrade. Try again after the upgrade is completed."))


def disk_wipe(device):
    """Wipe GPT table entries.
    We ignore exit codes in case disk is toasted or not present.
    Note: Assumption is that entire disk is used
    :param device: disk device node or device path
    """
    LOG.info("Wiping device: %s " % device)

    # Wipe well known GPT table entries, if any.
    trycmd('wipefs', '-f', '-a', device)
    execute('udevadm', 'settle')

    # Wipe any other tables at the beginning of the device.
    out, err = trycmd(
        'dd', 'if=/dev/zero',
        'of=%s' % device,
        'bs=512', 'count=2048',
        'conv=fdatasync')
    LOG.info("Wiped beginning of disk: %s - %s" % (out, err))

    # Get size of disk.
    size, __ = trycmd('blockdev', '--getsz',
                      device)
    size = size.rstrip()

    if size and size.isdigit():
        # Wipe at the end of device.
        out, err = trycmd(
            'dd', 'if=/dev/zero',
            'of=%s' % device,
            'bs=512', 'count=2048',
            'seek=%s' % (int(size) - 2048),
            'conv=fdatasync')
        LOG.info("Wiped end of disk: %s - %s" % (out, err))

    LOG.info("Device %s zapped" % device)


def get_dhcp_client_iaid(mac_address):
    """Retrieves the client IAID from its MAC address."""
    hwaddr = list(int(byte, 16) for byte in mac_address.split(':'))
    return hwaddr[2] << 24 | hwaddr[3] << 16 | hwaddr[4] << 8 | hwaddr[5]


def get_controller_fs_scratch_size():
    """ Get the filesystem scratch size setup by kickstart.
    """

    args = ["lvdisplay",
            "--columns",
            "--options",
            "lv_size,lv_name",
            "--units",
            "g",
            "--noheading",
            "--nosuffix",
            "/dev/cgts-vg/scratch-lv"]

    scratch_gib = 8

    with open(os.devnull, "w") as fnull:
        try:
            lvdisplay_output = subprocess.check_output(args, stderr=fnull)
        except subprocess.CalledProcessError:
            raise Exception("Failed to get controller filesystem scratch size")

        lvdisplay_dict = output_to_dict(lvdisplay_output)
        scratch_gib = int(math.ceil(float(lvdisplay_dict.get('scratch-lv'))))
        if not scratch_gib:
            # ConfigFail
            raise Exception("Unexpected scratch_gib=%s" % scratch_gib)

    return scratch_gib


def get_cgts_vg_free_space():
    """Determine free space in cgts-vg"""

    try:
        # Determine space in cgts-vg in GiB
        vg_free_str = subprocess.check_output(
            ['vgdisplay', '-C', '--noheadings', '--nosuffix',
             '-o', 'vg_free', '--units', 'g', 'cgts-vg'],
            close_fds=True).rstrip()
        cgts_vg_free = int(float(vg_free_str))
    except subprocess.CalledProcessError:
        LOG.error("Command vgdisplay failed")
        raise Exception("Command vgdisplay failed")

    return cgts_vg_free


def read_filtered_directory_content(dirpath, *filters):
    """ Reads the content of a directory, filtered on
    glob like expressions.

    Returns a dictionary, with the "key" being the filename
    and the "value" being the content of that file
    """
    def filter_directory_files(dirpath, *filters):
        return it.chain.from_iterable(glob.iglob(dirpath + '/' + filter)
                                      for filter in filters)

    content_dict = {}
    for filename in filter_directory_files(dirpath, *filters):
        content = ""
        with open(os.path.join(filename), 'rb') as obj:
            content = obj.read()
        try:
            # If the filter specified binary files then
            # these will need to be base64 encoded so that
            # they can be transferred over RPC and stored in DB
            content.decode('utf-8')
        except UnicodeError:
            content = content.encode('base64')
            content_dict['base64_encoded_files'] = \
                content_dict.get("base64_encoded_files", []) + [filename]

        content_dict[filename] = content
    return content_dict


def get_disk_capacity_mib(device_node):
    # Run command
    fdisk_command = 'fdisk -l %s | grep "^Disk %s:"' % (
        device_node, device_node)

    try:
        fdisk_output, _ = execute(fdisk_command, check_exit_code=[0],
                                  run_as_root=True, attempts=3,
                                  shell=True)
    except exception.ProcessExecutionError:
        LOG.error("Error running fdisk command: %s" %
                  fdisk_command)
        return 0

    # Parse output
    second_half = fdisk_output.split(',')[1]
    size_bytes = second_half.split()[0].strip()

    # Convert bytes to MiB (1 MiB = 1024*1024 bytes)
    int_size = int(size_bytes)
    size_mib = int_size / (1024**2)

    return int(size_mib)


def format_range_set(items):
    # Generate a pretty-printed value of ranges, such as 3-6,8-9,12-17
    ranges = []
    for k, iterable in it.groupby(enumerate(sorted(items)),
                                         lambda x: x[1] - x[0]):
        rng = list(iterable)
        if len(rng) == 1:
            s = str(rng[0][1])
        else:
            s = "%s-%s" % (rng[0][1], rng[-1][1])
        ranges.append(s)
    return ','.join(ranges)


def get_numa_index_list(obj):
    """Create map of objects indexed by numa node"""
    obj_lists = collections.defaultdict(list)
    for index, o in enumerate(obj):
        o["_index"] = index
        obj_lists[o.numa_node].append(o)
    return obj_lists


def _format_ceph_mon_address(ip_address, service_port_mon):
    if netaddr.IPAddress(ip_address).version == constants.IPV4_FAMILY:
        return '%s:%d' % (ip_address, service_port_mon)
    else:
        return '[%s]:%d' % (ip_address, service_port_mon)


def get_files_matching(path, pattern):
    return [(root, file) for root, dirs, files in os.walk(path, topdown=True)
            for file in files if file.endswith(pattern)]


def extract_tarfile(target_dir, tarfile):
    with open(os.devnull, "w") as fnull:
        try:
            subprocess.check_call(['tar', '-xf', tarfile, '-m', '--no-same-owner',
                                   '--no-same-permissions', '-C', target_dir],
                                  stdout=fnull, stderr=fnull)
            return True
        except subprocess.CalledProcessError as e:
            LOG.error("Error while extracting tarfile %s: %s" % (tarfile, e))
            return False


def is_openstack_installed(dbapi):
    """ Checks whether the OpenStack application is installed. """
    try:
        openstack_app = dbapi.kube_app_get(constants.HELM_APP_OPENSTACK)
        if openstack_app.status == constants.APP_APPLY_SUCCESS:
            return True
        else:
            return False
    except exception.KubeAppNotFound:
        return False
