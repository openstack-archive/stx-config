class platform::multipath::params (
  $enabled = false,
) {
}

class platform::multipath
  inherits platform::multipath::params {
  if $enabled {
    file { '/etc/multipath.conf':
      ensure  => 'present',
      mode    => '0644',
      content => template("platform/multipath.conf.erb")
    } ->
    exec { 'enable multipath':
      command => '/usr/sbin/mpathconf --enable --with-module y',
    } ->
    service { 'start-multipathd':
      ensure     => 'running',
      enable     => true,
      name       => 'multipathd',
      hasstatus  => true,
      hasrestart => true,
    }
  } else {
    service { 'start-multipathd':
      ensure     => 'stopped',
      enable     => false,
      name       => 'multipathd',
      hasstatus  => true,
      hasrestart => true,
    }
  }
}
