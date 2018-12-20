#
# Files in this package are licensed under Apache; see LICENSE file.
#
# Copyright (c) 2019 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#
#  Jan 2019: creation
#

# == Class: dbsync::keystone::auth
#
# Configures dbsync user, service and endpoint in Keystone.
#
class dbsync::keystone::auth (
  $password,
  $auth_name            = 'dbsync',
  $auth_domain,
  $email                = 'dbsync@localhost',
  $tenant               = 'services',
  $region               = 'RegionOne',
  $service_description  = 'DCOrch dbsync service',
  $service_name         = 'dbsync',
  $service_type         = 'dcorch-dbsync',
  $configure_endpoint   = true,
  $configure_user       = true,
  $configure_user_role  = true,
  $public_url           = 'http://127.0.0.1:8219/v1',
  $admin_url            = 'http://127.0.0.1:8219/v1',
  $internal_url         = 'http://127.0.0.1:8219/v1',
) {

  $real_service_name = pick($service_name, $auth_name)

  keystone::resource::service_identity { 'dbsync':
    configure_user      => $configure_user,
    configure_user_role => $configure_user_role,
    configure_endpoint  => $configure_endpoint,
    service_type        => $service_type,
    service_description => $service_description,
    service_name        => $real_service_name,
    region              => $region,
    auth_name           => $auth_name,
    password            => $password,
    email               => $email,
    tenant              => $tenant,
    public_url          => $public_url,
    admin_url           => $admin_url,
    internal_url        => $internal_url,
  }
}
