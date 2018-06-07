class platform::vswitch::params(
  $iommu_enabled = true,
  $hugepage_dir = '/mnt/huge-1048576kB',
  $driver_type = 'vfio-pci',
) { }


class platform::vswitch
  inherits ::platform::vswitch::params {

  Class[$name] -> Class['::platform::network']
  Mount[$hugepage_dir] -> Class[$name]

  $enable_unsafe_noiommu_mode = bool2num(!$iommu_enabled)

  exec {'vfio-iommu-mode':
    command => "echo ${enable_unsafe_noiommu_mode} > /sys/module/vfio/parameters/enable_unsafe_noiommu_mode",
    require => Kmod::Load[$driver_type],
  }

  include ::platform::vswitch::ovs
}


define platform::vswitch::ovs::device(
  $pci_addr,
  $driver_type,
) {
  exec { "ovs-bind-device: $title":
    path => ["/usr/bin", "/usr/sbin", "/usr/share/openvswitch/scripts"],
    command => "dpdk-devbind.py --bind=${driver_type} ${pci_addr}"
  }
}


define platform::vswitch::ovs::bridge(
  $datapath_type = 'netdev',
) {
  exec { "ovs-add-br: ${title}":
    command => template("platform/ovs.add-bridge.erb")
  } ->
  exec { "ovs-link-up: ${title}":
    command => "ip link set ${name} up",
  }
}


define platform::vswitch::ovs::port(
  $type = 'port',
  $bridge,
  $attributes = [],
  $interfaces,
) {
  exec { "ovs-add-port: ${title}":
    command => template("platform/ovs.add-port.erb"),
    logoutput => true
  }
}


define platform::vswitch::ovs::address(
  $ifname,
  $address,
  $prefixlen,
) {
  exec { "ovs-add-address: ${title}":
    command => "ip addr replace ${address}/${prefixlen} dev ${ifname}",
  }
}


class platform::vswitch::ovs(
  $devices = {},
  $bridges = {},
  $ports = {},
  $addresses = {},
) inherits ::platform::vswitch::params {

  if $::platform::params::vswitch_type == 'ovs' {
    include ::vswitch::ovs
  } elsif $::platform::params::vswitch_type == 'ovs-dpdk' {
    include ::vswitch::dpdk

    Exec['vfio-iommu-mode'] ->
    Platform::Vswitch::Ovs::Device<||> ->
    Platform::Vswitch::Ovs::Bridge<||>

    create_resources('platform::vswitch::ovs::device', $devices, {
      driver_type => $driver_type,
      before => Service['openvswitch']
    })

    $dpdk_configs = {
      'other_config:dpdk-hugepage-dir' => { value => $hugepage_dir },
    }

    $dpdk_dependencies = {
      wait    => false,
      require => Service['openvswitch'],
      notify  => Vs_config['other_config:dpdk-init'],
    }

    create_resources ('vs_config', $dpdk_configs, $dpdk_dependencies)
  }

  if $::platform::params::vswitch_type =~ '^ovs' {

    # clean bridges and ports before applying current configuration
    exec { "ovs-clean":
      command  => template("platform/ovs.clean.erb"),
      provider => shell,
      require  => Service['openvswitch']
    } ->

    Platform::Vswitch::Ovs::Bridge<||> -> Platform::Vswitch::Ovs::Port<||>
    Platform::Vswitch::Ovs::Bridge<||> -> Platform::Vswitch::Ovs::Address<||>
  }

  create_resources('platform::vswitch::ovs::bridge', $bridges, {
    require => Service['openvswitch']
  })

  create_resources('platform::vswitch::ovs::port', $ports, {
    require => Service['openvswitch']
  })

  create_resources('platform::vswitch::ovs::address', $addresses, {
    require => Service['openvswitch']
  })
}
