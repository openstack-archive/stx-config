class openstack::ceilometer::params (
  $api_port = 8777,
  $region_name = undef,
  $service_name = 'openstack-ceilometer',
  $service_create = false,
) { }


class openstack::ceilometer {
  include ::platform::amqp::params
  include ::platform::params
  include ::openstack::ceilometer::params

  class { '::ceilometer':
    rabbit_use_ssl            => $::platform::amqp::params::ssl_enabled,
    default_transport_url     => $::platform::amqp::params::transport_url,
    rabbit_qos_prefetch_count => 100,
  }

  if ($::openstack::ceilometer::params::service_create and
      $::platform::params::init_keystone) {
    include ::ceilometer::keystone::auth

  }

  include ::ceilometer::agent::auth
  include ::openstack::cinder::params
  include ::openstack::glance::params

  # FIXME(mpeters): generic parameter can be moved to the puppet module
  ceilometer_config {
    'DEFAULT/executor_thread_pool_size': value => 16;
    'DEFAULT/shuffle_time_before_polling_task': value => 30;
    'DEFAULT/batch_polled_samples': value => true;
    'oslo_messaging_rabbit/rpc_conn_pool_size': value => 10;
    'oslo_messaging_rabbit/socket_timeout': value => 1.00;
    'compute/resource_update_interval': value => 60;
    'DEFAULT/region_name_for_services':  value => $::openstack::ceilometer::params::region_name;
  }


  if $::personality == 'controller' {
    include ::platform::memcached::params

    $memcache_ip = $::platform::memcached::params::listen_ip
    $memcache_port = $::platform::memcached::params::tcp_port
    $memcache_ip_version = $::platform::memcached::params::listen_ip_version

    $memcache_servers = $memcache_ip_version ? {
      4 => "'${memcache_ip}:${memcache_port}'",
      6 => "'inet6:[${memcache_ip}]:${memcache_port}'",
    }

    oslo::cache { 'ceilometer_config':
      enabled          => true,
      backend          => 'dogpile.cache.memcached',
      memcache_servers => $memcache_servers,
      expiration_time  => 86400,
    }
  }

  if $::platform::params::region_config {
    if $::openstack::glance::params::region_name != $::platform::params::region_2_name {
      $shared_service_glance = [$::openstack::glance::params::service_type]
    } else {
      $shared_service_glance = []
    }
    # skip the check if cinder region name has not been configured
    if ($::openstack::cinder::params::region_name != undef and
        $::openstack::cinder::params::region_name != $::platform::params::region_2_name) {
      $shared_service_cinder = [$::openstack::cinder::params::service_type,
                                $::openstack::cinder::params::service_type_v2,
                                $::openstack::cinder::params::service_type_v3]
    } else {
      $shared_service_cinder = []
    }
    $shared_services = concat($shared_service_glance, $shared_service_cinder)
    ceilometer_config {
      'DEFAULT/region_name_for_shared_services':  value => $::platform::params::region_1_name;
      'DEFAULT/shared_services_types': value => join($shared_services,',');
    }
  }

}


class openstack::ceilometer::agent::notification {
  include ::platform::params

  $cgcs_fs_directory    = '/opt/cgcs'
  $ceilometer_directory = "${cgcs_fs_directory}/ceilometer"
  $ceilometer_directory_csv = "${ceilometer_directory}/csv"
  $ceilometer_directory_versioned = "${ceilometer_directory}/${::platform::params::software_version}"

  file { '/etc/ceilometer/pipeline.yaml':
    ensure  => 'present',
    content => template('openstack/pipeline.yaml.erb'),
    mode    => '0640',
    owner   => 'root',
    group   => 'ceilometer',
    tag     => 'ceilometer-yamls',
  }
  -> file { $ceilometer_directory:
    ensure => 'directory',
    owner  => 'root',
    group  => 'root',
    mode   => '0755',
  }
  -> file { $ceilometer_directory_csv:
    ensure => 'directory',
    owner  => 'root',
    group  => 'root',
    mode   => '0755',
  }
  -> file { $ceilometer_directory_versioned:
    ensure => 'directory',
    owner  => 'root',
    group  => 'root',
    mode   => '0755',
  }
  -> file { "${ceilometer_directory_versioned}/pipeline.yaml":
    ensure => 'file',
    source => '/etc/ceilometer/pipeline.yaml',
    owner  => 'root',
    group  => 'root',
    mode   => '0640',
  }

  file { '/etc/ceilometer/gnocchi_resources.yaml':
    ensure  => 'present',
    content => template('openstack/gnocchi_resources.yaml.erb'),
    mode    => '0640',
    owner   => 'root',
    group   => 'ceilometer',
    tag     => 'ceilometer-yamls',
  }

  # Limit the number of ceilometer agent notification workers to 10 max
  $agent_workers_count = min($::platform::params::eng_workers_by_2, 10)

  if $::platform::params::system_type == 'All-in-one' {
    $batch_timeout = 25
  } else {
    $batch_timeout = 5
  }

  # FIXME(mpeters): generic parameter can be moved to the puppet module
  ceilometer_config {
    'DEFAULT/csv_location': value => $ceilometer_directory_csv;
    'DEFAULT/csv_location_strict': value => true;
    'notification/workers': value => $agent_workers_count;
    'notification/batch_size': value => 100;
    'notification/batch_timeout': value => $batch_timeout;
  }
}


class openstack::ceilometer::polling (
  $instance_polling_interval       = 600,
  $instance_cpu_polling_interval   = 30,
  $instance_disk_polling_interval  = 600,
  $ipmi_polling_interval           = 600,
  $ceph_polling_interval           = 600,
  $image_polling_interval          = 600,
  $volume_polling_interval         = 600,
) {
  include ::platform::params

  file { '/etc/ceilometer/polling.yaml':
    ensure  => 'present',
    content => template('openstack/polling.yaml.erb'),
    mode    => '0640',
    owner   => 'root',
    group   => 'ceilometer',
    tag     => 'ceilometer-yamls',
  }

  if $::personality == 'controller' {
    $central_namespace = true
  } else {
    $central_namespace = false
  }

  $agent_enable = false
  $compute_namespace = false

  file { '/etc/pmon.d/ceilometer-polling.conf':
    ensure  => absent,
  }

  class { '::ceilometer::agent::polling':
    enabled           => $agent_enable,
    central_namespace => $central_namespace,
    compute_namespace => $compute_namespace,
  }
}
