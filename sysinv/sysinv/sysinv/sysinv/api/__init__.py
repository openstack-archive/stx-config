# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2013 Hewlett-Packard Development Company, L.P.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from oslo_config import cfg


API_SERVICE_OPTS = [
    cfg.StrOpt('sysinv_api_bind_ip',
               default='0.0.0.0',
               help='IP for the Sysinv API server to bind to'),
    cfg.IntOpt('sysinv_api_port',
               default=6385,
               help='The port for the Sysinv API server'),
    cfg.StrOpt('sysinv_api_pxeboot_ip',
               help='IP for the Sysinv API server to bind to'),
    cfg.IntOpt('sysinv_api_workers',
               help='Number of api workers for the SysInv API'),
    cfg.IntOpt('api_limit_max',
               default=2000,
               help='the maximum number of items returned in a single '
               'response from a collection resource')
]

CONF = cfg.CONF
opt_group = cfg.OptGroup(name='api',
                         title='Options for the sysinv-api service')
CONF.register_group(opt_group)
CONF.register_opts(API_SERVICE_OPTS)
