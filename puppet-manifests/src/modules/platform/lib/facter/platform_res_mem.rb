Facter.add(:platform_res_mem) do
  setcode "grep -e Avail -e anon /proc/meminfo | awk '{a+=$2} END{print int(a/1024)}'"
end
