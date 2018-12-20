class platform::dbsync::params (
  $api_port = 8219,
  $region_name = undef,
  $service_name = 'dbsync-api',
  $service_create = false,
  $service_enabled = true,
  $default_endpoint_type = 'internalURL',
) { }

class platform::dbsync
  inherits ::platform::dbsync::params {

  if $service_enabled {

    include ::platform::params

    if $::platform::params::init_keystone {
      include ::dbsync::keystone::auth
    }

    class { '::dbsync': }
  }
}

class platform::dbsync::api
  inherits ::platform::dbsync::params {
  include ::platform::params

  if $service_enabled {
    include ::platform::network::mgmt::params
    $api_host = $::platform::network::mgmt::params::controller_address
    $api_fqdn = $::platform::params::controller_hostname
    $url_host = "http://${api_fqdn}:${api_port}"

    include ::platform::amqp::params

    class { '::dbsync::api':
      bind_host => $api_host,
      bind_port => $api_port,
    }
  }
}

