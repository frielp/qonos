# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    Copyright 2013 Rackspace
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

import logging as pylog

from qonos.openstack.common import cfg
from qonos.openstack.common.gettextutils import _
import qonos.openstack.common.log as logging
import qonos.openstack.common.wsgi as wsgi

LOG = logging.getLogger(__name__)

api_opts = [
    cfg.BoolOpt('daemonized', default=False),
    cfg.IntOpt('port', default=8080),
]

CONF = cfg.CONF
CONF.register_opts(api_opts, group='api')


class API(object):
    def __init__(self, app, product_name='qonos'):
        self.app = app
        self.product_name = product_name

    def run(self, run_once=False):
        LOG.debug(_('Starting qonos-api service'))

        if CONF.api.daemonized:
            import daemon
            #NOTE(ameade): We need to preserve all open files for logging
            open_files = []
            for handler in pylog.getLogger(self.product_name).handlers:
                if (hasattr(handler, 'stream') and
                        hasattr(handler.stream, 'fileno')):
                    open_files.append(handler.stream)
            LOG.debug(_('Open files: %s') % str(open_files))
            with daemon.DaemonContext(files_preserve=open_files):
                wsgi.run_server(self.app, CONF.api.port)
        else:
            wsgi.run_server(self.app, CONF.api.port)
