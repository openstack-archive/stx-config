class platform::lvm::params (
  $transition_filter = '[]',
  $final_filter = '[]',
) {}


class platform::lvm
  inherits platform::lvm::params {

  file_line { 'use_lvmetad':
    path    => '/etc/lvm/lvm.conf',
    match   => '^[^#]*use_lvmetad = 1',
    line    => '        use_lvmetad = 0',
  }

  exec { 'disable lvm2-lvmetad.service':
    command => "systemctl stop lvm2-lvmetad.service ; systemctl disable lvm2-lvmetad.service",
    onlyif  => "systemctl status lvm2-lvmetad.service",
  }
}


define platform::lvm::global_filter($filter) {
  file_line { "$name: update lvm global_filter":
    path  => '/etc/lvm/lvm.conf',
    line  => "    global_filter = $filter",
    match => '^[ ]*global_filter =',
  }
}


define platform::lvm::umount {
  exec { "umount disk $name":
    command => "umount $name; true",
  }
}


class platform::lvm::vg::cgts_vg(
  $vg_name = 'cgts-vg',
  $physical_volumes = [],
) inherits platform::lvm::params {

  ::platform::lvm::umount { $physical_volumes:
  } ->
  physical_volume { $physical_volumes:
    ensure => present,
  } ->
  volume_group { $vg_name:
    ensure => present,
    physical_volumes => $physical_volumes,
  }
}

class platform::lvm::vg::cinder_volumes(
  $vg_name = 'cinder-volumes',
  $physical_volumes = [],
) inherits platform::lvm::params {
  # Let cinder manifests set up DRBD synced volume group
}

class platform::lvm::vg::nova_local(
  $vg_name = 'nova-local',
  $physical_volumes = [],
) inherits platform::lvm::params {
  # TODO(rchurch): refactor portions of openstack::nova::storage an move here
}

##################
# Controller Hosts
##################

class platform::lvm::controller::vgs {
  include ::platform::lvm::vg::cgts_vg
  include ::platform::lvm::vg::cinder_volumes
  include ::platform::lvm::vg::nova_local
}

class platform::lvm::controller
  inherits ::platform::lvm::params {

  ::platform::lvm::global_filter { "transition filter":
    filter => $transition_filter,
    before => Class['::platform::lvm::controller::vgs']
  }

  ::platform::lvm::global_filter { "final filter":
    filter => $final_filter,
    require => Class['::platform::lvm::controller::vgs']
  }

  include ::platform::lvm
  include ::platform::lvm::controller::vgs
}


class platform::lvm::controller::runtime {
  include ::platform::lvm::controller
}

###############
# Compute Hosts
###############

class platform::lvm::compute::vgs {
  include ::platform::lvm::vg::nova_local
  include ::platform::kubernetes::params

  if $::platform::kubernetes::params::enabled {
    include ::platform::lvm::vg::cgts_vg
  }
}

class platform::lvm::compute
  inherits ::platform::lvm::params {

  ::platform::lvm::global_filter { "transition filter":
    filter => $transition_filter,
    before => Class['::platform::lvm::compute::vgs']
  }

  ::platform::lvm::global_filter { "final filter":
    filter => $final_filter,
    require => Class['::platform::lvm::compute::vgs']
  }

  include ::platform::lvm
  include ::platform::lvm::compute::vgs
}


class platform::lvm::compute::runtime {
  include ::platform::lvm::compute
}

###############
# Storage Hosts
###############

class platform::lvm::storage::vgs {
  include ::platform::lvm::vg::cgts_vg
}

class platform::lvm::storage
  inherits ::platform::lvm::params {

  ::platform::lvm::global_filter { "final filter":
    filter => $final_filter,
    before => Class['::platform::lvm::storage::vgs']
  }

  include ::platform::lvm
  include ::platform::lvm::storage::vgs
}


class platform::lvm::storage::runtime {
  include ::platform::lvm::storage
}
