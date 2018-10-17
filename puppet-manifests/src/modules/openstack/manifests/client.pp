class openstack::client
  inherits ::platform::client::params {

  include ::platform::client::credentials::params
  $keyring_file = $::platform::client::credentials::params::keyring_file

  file {"/etc/nova/openrc":
    ensure  => "present",
    mode    => '0640',
    owner   => 'nova',
    group   => 'root',
    content => template('openstack/openrc.admin.erb'),
  }

  file {"/etc/nova/ldap_openrc_template":
    ensure  => "present",
    mode    => '0644',
    content => template('openstack/openrc.ldap.erb'),
  }

  file {"/etc/bash_completion.d/openstack":
    ensure  => "present",
    mode    => '0644',
    content => generate('/usr/bin/openstack', 'complete'),
  }
}

class openstack::client::bootstrap {
  include ::openstack::client
}

class openstack::client::upgrade {
  include ::openstack::client
}
