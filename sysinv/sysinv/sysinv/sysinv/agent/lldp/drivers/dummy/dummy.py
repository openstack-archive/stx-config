#
# Copyright (c) 2018 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

# vim: tabstop=4 shiftwidth=4 softtabstop=4

# All Rights Reserved.
#

from oslo_log import helpers as log_helpers

from sysinv.agent.lldp.drivers import base as lldp_driver


class DummyDriver(lldp_driver.SysinvLldpDriverBase):
    """Sysinv LLDP Driver Dummy Class."""
    def initialize(self):
        pass

    def lldp_agents_list(self):
        return []

    def lldp_neighbours_list(self):
        return []

    def lldp_agents_clear(self):
        pass

    def lldp_neighbours_clear(self):
        pass

    def lldp_update_systemname(self, systemname):
        pass
