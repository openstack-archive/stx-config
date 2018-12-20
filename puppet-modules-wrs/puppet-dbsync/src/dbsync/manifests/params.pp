#
# Files in this package are licensed under Apache; see LICENSE file.
#
# Copyright (c) 2019 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#
#

class dbsync::params {

  $dbsync_dir = '/etc/dbsync'
  $dbsync_conf = '/etc/dbsync/dbsync.conf'

  if $::osfamily == 'Debian' {
    $package_name       = 'distributedcloud-dbsync'
    $api_package        = 'distributedcloud-dbsync'
    $api_service        = 'dbsync-api'

  } elsif($::osfamily == 'RedHat') {

    $package_name       = 'distributedcloud-dbsync'
    $api_package        = false
    $api_service        = 'dbsync-api'

  } elsif($::osfamily == 'WRLinux') {

    $package_name       = 'dbsync'
    $api_package        = false
    $api_service        = 'dbsync-api'

  } else {
    fail("unsuported osfamily ${::osfamily}, currently WindRiver, Debian, Redhat are the only supported platforms")
  }
}
