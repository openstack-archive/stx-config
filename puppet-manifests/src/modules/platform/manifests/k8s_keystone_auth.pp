class platform::k8s_keystone_auth::configkubectl {

  Class['::platform::helm'] -> Class[$name]

  if ! str2bool($::is_initial_config_primary) {
    # Config Kubectl Client to use Keystone
    exec { 'Configure kubectl client':
      command   => 'kubectl --kubeconfig=/etc/kubernetes/admin.conf config set-credentials openstackuser --auth-provider=openstack',
      logoutput => true,
    }

    # Create new context to use Keystone as Auth Backend
    -> exec { 'Create new context for kubectl':
      command   => "kubectl --kubeconfig=/etc/kubernetes/admin.conf config set-context --cluster=kubernetes \
                     --user=openstackuser openstackuser@kubernetes",
      logoutput => true,
    }

    -> exec { 'Switch context for Keystone Auth':
      command   => 'kubectl --kubeconfig=/etc/kubernetes/admin.conf config use-context openstackuser@kubernetes',
      logoutput => true,
    }
  }
}

class platform::k8s_keystone_auth {

  include ::platform::kubernetes::params

  if $::platform::kubernetes::params::enabled {
    contain ::platform::k8s_keystone_auth::configkubectl

    Class['::platform::kubernetes::master'] -> Class[$name]
  }
}
