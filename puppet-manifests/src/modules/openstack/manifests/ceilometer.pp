class openstack::ceilometer::params (
  $api_port = 8777,
  $region_name = undef,
  $service_name = 'openstack-ceilometer',
  $service_create = false,
) { }


class openstack::ceilometer {
  include ::platform::amqp::params

  class { '::ceilometer':
    rabbit_use_ssl => $::platform::amqp::params::ssl_enabled,
    default_transport_url => $::platform::amqp::params::transport_url,
    rabbit_qos_prefetch_count => 100,
  }

  if ($::openstack::ceilometer::params::service_create and
      $::platform::params::init_keystone) {
    include ::ceilometer::keystone::auth
  }

  include ::ceilometer::agent::auth
  include ::platform::params
  include ::openstack::ceilometer::params
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

  oslo::cache { 'ceilometer_config':
    enabled => true,
    backend => 'dogpile.cache.memory',
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

  file { "${ceilometer_directory}":
    ensure  => 'directory',
    owner   => 'root',
    group   => 'root',
    mode    => '0755',
  } ->
  file { "${ceilometer_directory_csv}":
    ensure  => 'directory',
    owner   => 'root',
    group   => 'root',
    mode    => '0755',
  } ->
  file { "${ceilometer_directory_versioned}":
    ensure  => 'directory',
    owner   => 'root',
    group   => 'root',
    mode    => '0755',
  } ->
  file { "${ceilometer_directory_versioned}/pipeline.yaml":
    source => '/etc/ceilometer/controller.yaml',
    ensure  => 'file',
    owner   => 'root',
    group   => 'root',
    mode    => '0640',
  }

  class { '::ceilometer::agent::notification':
    notification_workers  => $::platform::params::eng_workers_by_2,
  }

  if $::platform::params::system_type == 'All-in-one' {
    $batch_timeout = 25
  } else {
    $batch_timeout = 5
  }

  # FIXME(mpeters): generic parameter can be moved to the puppet module
  ceilometer_config {
    'DEFAULT/csv_location': value => "${ceilometer_directory_csv}";
    'DEFAULT/csv_location_strict': value => true;
    'service_credentials/interface': value => 'internalURL';
    'notification/batch_size': value => 100;
    'notification/batch_timeout': value => $batch_timeout;
  }
}


class openstack::ceilometer::polling {
  include ::platform::params

  if $::personality == 'controller' {
    $central_namespace = true
  } else {
    $central_namespace = false
  }

  if str2bool($::disable_compute_services) {
    $agent_enable = false
    $compute_namespace = false

    file { '/etc/pmon.d/ceilometer-polling.conf':
       ensure  => absent,
    }
  } else {
    $agent_enable = true

    if str2bool($::is_compute_subfunction) {
      $pmon_target = "/etc/ceilometer/ceilometer-polling-compute.conf.pmon"
      $compute_namespace = true
    } else {
      $pmon_target = "/etc/ceilometer/ceilometer-polling.conf.pmon"
      $compute_namespace = false
    }

    file { "/etc/pmon.d/ceilometer-polling.conf":
      ensure => link,
      target => $pmon_target,
      owner   => 'root',
      group   => 'root',
      mode    => '0640',
    }
  }

  class { '::ceilometer::agent::polling':
    enabled => $agent_enable,
    central_namespace => $central_namespace,
    compute_namespace => $compute_namespace,
  }
}
