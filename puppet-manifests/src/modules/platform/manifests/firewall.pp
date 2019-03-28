define platform::firewall::rule (
  $service_name,
  $chain = 'INPUT',
  $destination = undef,
  $ensure = present,
  $host = 'ALL',
  $jump  = undef,
  $outiface = undef,
  $ports = undef,
  $proto = 'tcp',
  $table = undef,
  $tosource = undef,
) {

  include ::platform::params
  include ::platform::network::oam::params

  $ip_version = $::platform::network::oam::params::subnet_version

  $provider = $ip_version ? {
    6 => 'ip6tables',
    default => 'iptables',
  }

  $source = $host ? {
    'ALL' => $ip_version ? {
      6  => '::/0',
      default => '0.0.0.0/0'
    },
    default => $host,
  }

  $heading = $chain ? {
    'OUTPUT' => 'outgoing',
    'POSTROUTING' => 'forwarding',
    default => 'incoming',
  }

  # NAT rule
  if $jump == 'SNAT' or $jump == 'MASQUERADE' {
    firewall { "500 ${service_name} ${heading} ${title}":
      ensure      => $ensure,
      table       => $table,
      proto       => $proto,
      outiface    => $outiface,
      jump        => $jump,
      tosource    => $tosource,
      destination => $destination,
      source      => $source,
      provider    => $provider,
      chain       => $chain,
    }
  }
  else {
    if $ports == undef {
      firewall { "500 ${service_name} ${heading} ${title}":
        ensure   => $ensure,
        proto    => $proto,
        action   => 'accept',
        source   => $source,
        provider => $provider,
        chain    => $chain,
      }
    }
    else {
      firewall { "500 ${service_name} ${heading} ${title}":
        ensure   => $ensure,
        proto    => $proto,
        dport    => $ports,
        action   => 'accept',
        source   => $source,
        provider => $provider,
        chain    => $chain,
      }
    }
  }
}


define platform::firewall::common (
  $version,
  $interface,
) {

  $provider = $version ? {'ipv4' => 'iptables', 'ipv6' => 'ip6tables'}

  firewall { "000 platform accept non-oam ${version}":
    proto    => 'all',
    iniface  => "! ${$interface}",
    action   => 'accept',
    provider => $provider,
  }

  firewall { "001 platform accept related ${version}":
    proto    => 'all',
    state    => ['RELATED', 'ESTABLISHED'],
    action   => 'accept',
    provider => $provider,
  }

  # explicitly drop some types of traffic without logging
  firewall { "800 platform drop tcf-agent udp ${version}":
    proto    => 'udp',
    dport    => 1534,
    action   => 'drop',
    provider => $provider,
  }

  firewall { "800 platform drop tcf-agent tcp ${version}":
    proto    => 'tcp',
    dport    => 1534,
    action   => 'drop',
    provider => $provider,
  }

  firewall { "800 platform drop all avahi-daemon ${version}":
    proto    => 'udp',
    dport    => 5353,
    action   => 'drop',
    provider => $provider,
  }

  firewall { "999 platform log dropped ${version}":
    proto      => 'all',
    limit      => '2/min',
    jump       => 'LOG',
    log_prefix => "${provider}-in-dropped: ",
    log_level  => 4,
    provider   => $provider,
  }

  firewall { "000 platform forward non-oam ${version}":
    chain    => 'FORWARD',
    proto    => 'all',
    iniface  => "! ${interface}",
    action   => 'accept',
    provider => $provider,
  }

  firewall { "001 platform forward related ${version}":
    chain    => 'FORWARD',
    proto    => 'all',
    state    => ['RELATED', 'ESTABLISHED'],
    action   => 'accept',
    provider => $provider,
  }

  firewall { "999 platform log dropped ${version} forwarded":
    chain      => 'FORWARD',
    proto      => 'all',
    limit      => '2/min',
    jump       => 'LOG',
    log_prefix => "${provider}-fwd-dropped: ",
    log_level  => 4,
    provider   => $provider,
  }
}

# Declare OAM service rules
define platform::firewall::services (
  $version,
) {
  # platform rules to be applied before custom rules
  Firewall {
    require => undef,
  }

  $provider = $version ? {'ipv4' => 'iptables', 'ipv6' => 'ip6tables'}

  $proto_icmp = $version ? {'ipv4' => 'icmp', 'ipv6' => 'ipv6-icmp'}

  # Provider specific service rules
  firewall { "010 platform accept sm ${version}":
    proto    => 'udp',
    dport    => [2222, 2223],
    action   => 'accept',
    provider => $provider,
  }

  firewall { "011 platform accept ssh ${version}":
    proto    => 'tcp',
    dport    => 22,
    action   => 'accept',
    provider => $provider,
  }

  firewall { "200 platform accept icmp ${version}":
    proto    => $proto_icmp,
    action   => 'accept',
    provider => $provider,
  }

  firewall { "201 platform accept ntp ${version}":
    proto    => 'udp',
    dport    => 123,
    action   => 'accept',
    provider => $provider,
  }

  firewall { "202 platform accept snmp ${version}":
    proto    => 'udp',
    dport    => 161,
    action   => 'accept',
    provider => $provider,
  }

  firewall { "202 platform accept snmp trap ${version}":
    proto    => 'udp',
    dport    => 162,
    action   => 'accept',
    provider => $provider,
  }

  firewall { "203 platform accept ptp ${version}":
    proto    => 'udp',
    dport    => [319, 320],
    action   => 'accept',
    provider => $provider,
  }

  # allow IGMP Query traffic if IGMP Snooping is
  # enabled on the TOR switch
  firewall { "204 platform accept igmp ${version}":
    proto    => 'igmp',
    action   => 'accept',
    provider => $provider,
  }
}


define platform::firewall::hooks (
  $version = undef,
) {
  $protocol = $version ? {'ipv4' => 'IPv4', 'ipv6' => 'IPv6'}

  $input_pre_chain = 'INPUT-custom-pre'
  $input_post_chain = 'INPUT-custom-post'

  firewallchain { "${input_pre_chain}:filter:${protocol}":
    ensure => present,
  }
  -> firewallchain { "${input_post_chain}:filter:${protocol}":
    ensure => present,
  }
  -> firewall { "100 ${input_pre_chain} ${version}":
    proto => 'all',
    chain => 'INPUT',
    jump  => $input_pre_chain
  }
  -> firewall { "900 ${input_post_chain} ${version}":
    proto => 'all',
    chain => 'INPUT',
    jump  => $input_post_chain
  }
}


class platform::firewall::custom (
  $version = undef,
  $rules_file = undef,
) {

  $restore = $version ? {
    'ipv4' => 'iptables-restore',
    'ipv6' => 'ip6tables-restore'}

  platform::firewall::hooks { '::platform:firewall:hooks':
    version => $version,
  }

  -> exec { 'Flush firewall custom pre rules':
    command => 'iptables --flush INPUT-custom-pre',
  }
  -> exec { 'Flush firewall custom post rules':
    command => 'iptables --flush INPUT-custom-post',
  }
  -> exec { 'Apply firewall custom rules':
    command => "${restore} --noflush ${rules_file}",
  }
}

define platform::firewall::calico::rule (
  String $svc_name,
  String $svc_proto,
  Variant[Array, Undef] $svc_ports = undef,
  Integer $svc_order = 100,
) {
  include ::platform::network::oam::params

  $file_name = "/tmp/gnp_oam_${svc_name}.yaml"
  $ip_version = $::platform::network::oam::params::subnet_version

  $t_svc_name = $svc_name
  $t_svc_order = $svc_order

  if $svc_ports != undef {
    $t_ip_version = $ip_version
    $t_svc_ports = $svc_ports
    $t_svc_proto = $svc_proto
  }
  else {
    $t_ip_version = undef
    $t_svc_ports = undef
    case $svc_proto {
      'ICMP': {
        $t_svc_proto = $ip_version ? {
                          6 => 'ICMPv6',
                          default => 'ICMP'
                       }
      }
      'IGMP': {
        $t_svc_proto = 2
      }
      default: {
        err('Service proto is not supported!')
      }
    }
  }

  notice("t_svc_name: $t_svc_name")
  notice("t_ip_version: $t_ip_version")
  notice("t_svc_ports: $t_svc_ports")
  notice("t_svc_proto: $t_svc_proto")
  file { "$file_name":
      ensure  => file,
      content => template('platform/calico_oam_svc_gnp.yaml.erb'),
      owner   => 'root',
      group   => 'root',
      mode    => '0640',
  }
  -> exec { "apply resource $file_name":
    path    => '/usr/bin:/usr/sbin:/bin',
    command => "kubectl --kubeconfig=/etc/kubernetes/admin.conf apply -f $file_name",
  }
}

class platform::firewall::calico::oam::services {
  # sm
  platform::firewall::calico::rule { 'global network policy for sm':
    svc_name => "sm",
    svc_proto => "UDP",
    svc_ports => [2222, 2223],
  }

  # ssh
  platform::firewall::calico::rule { 'global network policy for ssh':
    svc_name => "ssh",
    svc_proto => "TCP",
    svc_ports => [22],
  }

  # icmp
  platform::firewall::calico::rule { 'global network policy for icmp':
    svc_name => "icmp",
    svc_proto => "ICMP",
  }

  # igmp
  platform::firewall::calico::rule { 'global network policy for igmp':
    svc_name => "igmp",
    svc_proto => "IGMP",
  }

  # ntp
  platform::firewall::calico::rule { "global network policy for ntp":
    svc_name => "ntp",
    svc_proto => "UDP",
    svc_ports => [123],
  }

  # snmp
  platform::firewall::calico::rule { "global network policy for snmp":
    svc_name => "snmp",
    svc_proto => "UDP",
    svc_ports => [161, 162],
  }

  # ptp
  platform::firewall::calico::rule { "global network policy for ptp":
    svc_name => "ptp",
    svc_proto => "UDP",
    svc_ports => [319, 320],
  }

  # fm
  include ::platform::fm::params
  notice("fm enabled: $::platform::fm::params::service_enabled")
  if $::platform::fm::params::service_enabled {
    platform::firewall::calico::rule { 'global network policy for fm-api':
      svc_name => "fm",
      svc_proto => "TCP",
      svc_ports => [$::platform::fm::params::api_port],
    }
  }

  # nfv-vim
  include ::platform::nfv::params
  platform::firewall::calico::rule { 'global network policy for nfv-vim-api':
      svc_name => "nfv-vim",
      svc_proto => "TCP",
      svc_ports => [$::platform::nfv::params::api_port],
  }

  # patching
  include ::platform::patching::params
  platform::firewall::calico::rule { 'global network policy for patching-api':
      svc_name => "patching",
      svc_proto => "TCP",
      svc_ports => [$::platform::patching::params::public_port],
  }

  # sysinv
  include ::platform::sysinv::params
  platform::firewall::calico::rule { 'global network policy for sysinv-api':
      svc_name => "sysinv",
      svc_proto => "TCP",
      svc_ports => [$::platform::sysinv::params::api_port],
  }

  # smapi
  include ::platform::smapi::params
  platform::firewall::calico::rule { 'global network policy for sm-api':
      svc_name => "sm-api",
      svc_proto => "TCP",
      svc_ports => [$::platform::smapi::params::port],
  }

  # ceph
  include ::platform::ceph::params
  platform::firewall::calico::rule { 'global network policy for ceph-radosgw':
      svc_name => "ceph-radosgw",
      svc_proto => "TCP",
      svc_ports => [$::platform::ceph::params::rgw_port],
  }

  # barbican
  include ::openstack::barbican::params
  platform::firewall::calico::rule { 'global network policy for barbican-api':
      svc_name => "barbican-api",
      svc_proto => "TCP",
      svc_ports => [$::openstack::barbican::params::api_port],
  }

  # keystone
  include ::openstack::keystone::params
  platform::firewall::calico::rule { 'global network policy for keystone-api':
      svc_name => "keystone",
      svc_proto => "TCP",
      svc_ports => [$::openstack::keystone::params::api_port],
  }

  # horizon
  include ::platform::params
  include ::openstack::horizon::params
  if $::platform::params::distributed_cloud_role != 'subcloud'  {
    if $::openstack::horizon::params::enable_https {
      $horizon_port = $::openstack::horizon::params::https_port
    } else {
      $horizon_port = $::openstack::horizon::params::http_port
    }

    platform::firewall::calico::rule { 'global network policy for dashboard':
      svc_name => "horizon",
      svc_proto => "TCP",
      svc_ports => [$horizon_port],
    }
  }

  # dcmanager
  include ::platform::dcmanager::params
  if $::platform::params::distributed_cloud_role == 'systemcontroller' {
    platform::firewall::calico::rule { 'global network policy for dcmanager-api':
      svc_name => "dcmanager",
      svc_proto => "TCP",
      svc_ports => [$::platform::dcmanager::params::api_port],
    }
  }

  # dcorch
  include ::platform::dcorch::params
  if $::platform::params::distributed_cloud_role == 'systemcontroller' {
    platform::firewall::calico::rule { 'global network policy for dcorch-sysinv-api-proxy':
      svc_name => "dcorch-sysinv-api-proxy",
      svc_proto => "TCP",
      svc_ports => [$::platform::dcorch::params::sysinv_api_proxy_port],
    }
    platform::firewall::calico::rule { 'global network policy for dcorch-patch-api-proxy':
      svc_name => "dcorch-patch-api-proxy",
      svc_proto => "TCP",
      svc_ports => [$::platform::dcorch::params::patch_api_proxy_port],
    }
    platform::firewall::calico::rule { 'global network policy for dcorch-identity-api-proxy':
      svc_name => "dcorch-identity-api-proxy",
      svc_proto => "TCP",
      svc_ports => [$::platform::dcorch::params::identity_api_proxy_port],
    }
  }
}

class platform::firewall::calico::oam::endpoints {
  include ::platform::params
  include ::platform::network::oam::params

  $host = $::platform::params::hostname
  $oam_if = $::platform::network::oam::params::interface_name
  $oam_addr = $::platform::network::oam::params::interface_address

  $t_ip_version = $::platform::network::oam::params::subnet_version

  notice("host: $host")
  notice("oam_if: $oam_if")
  notice("oam_addr: $oam_addr")

  # create/update oam host endpoint
  $file_name_hep = "/tmp/hep_${host}_oam.yaml"
  $file_name_gnp = '/tmp/gnp_outbound_oam.yaml'
  file { "$file_name_hep":
    ensure  => file,
    content => template('platform/calico_oam_hep.yaml.erb'),
    owner   => 'root',
    group   => 'root',
    mode    => '0640',
  }
  -> exec { "apply resource $file_name_hep":
    path    => '/usr/bin:/usr/sbin:/bin',
    command => "kubectl --kubeconfig=/etc/kubernetes/admin.conf apply -f $file_name_hep",
  }
  -> file { "$file_name_gnp":
    ensure => file,
    content => template('platform/calico_oam_outbound_gnp.yaml.erb'),
    owner   => 'root',
    group   => 'root',
    mode    => '0640',
  }
  -> exec { "apply resource $file_name_gnp":
    path    => '/usr/bin:/usr/sbin:/bin',
    command => "kubectl --kubeconfig=/etc/kubernetes/admin.conf apply -f $file_name_gnp",
  }
}

class platform::firewall::calico::oam {
  contain ::platform::firewall::calico::oam::endpoints
  contain ::platform::firewall::calico::oam::services

  Class['::platform::kubernetes::master'] -> Class[$name]
  Class['::platform::firewall::calico::oam::endpoints']
  -> Class['::platform::firewall::calico::oam::services']
}

class platform::firewall::oam (
  $rules_file = undef,
) {

  include ::platform::network::oam::params
  $interface_name = $::platform::network::oam::params::interface_name
  $subnet_version = $::platform::network::oam::params::subnet_version

  $version = $subnet_version ? {
    4 => 'ipv4',
    6 => 'ipv6',
  }

  platform::firewall::common { 'platform:firewall:ipv4':
    interface => $interface_name,
    version   => 'ipv4',
  }

  -> platform::firewall::common { 'platform:firewall:ipv6':
    interface => $interface_name,
    version   => 'ipv6',
  }

  -> platform::firewall::services { 'platform:firewall:services':
    version => $version,
  }

  # Set default table policies
  -> firewallchain { 'INPUT:filter:IPv4':
    ensure => present,
    policy => drop,
    before => undef,
    purge  => false,
  }

  -> firewallchain { 'INPUT:filter:IPv6':
    ensure => present,
    policy => drop,
    before => undef,
    purge  => false,
  }

  -> firewallchain { 'FORWARD:filter:IPv4':
    ensure => present,
    policy => drop,
    before => undef,
    purge  => false,
  }

  -> firewallchain { 'FORWARD:filter:IPv6':
    ensure => present,
    policy => drop,
    before => undef,
    purge  => false,
  }

  if $rules_file {

    class { '::platform::firewall::custom':
      version    => $version,
      rules_file => $rules_file,
    }
  }
}


class platform::firewall::runtime {
  include ::platform::firewall::oam
}
