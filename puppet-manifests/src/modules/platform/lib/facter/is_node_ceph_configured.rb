# Returns true if cinder Ceph needs to be configured on current node

Facter.add("is_node_ceph_configured") do
  setcode do
    File.exist?('/etc/platform/.node_ceph_configured')
  end
end
