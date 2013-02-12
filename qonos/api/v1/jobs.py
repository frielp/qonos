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

import webob.exc

from qonos.api.v1 import api_utils
from qonos.common import exception
from qonos.common import utils
import qonos.db
from qonos.openstack.common.gettextutils import _
from qonos.openstack.common import timeutils
from qonos.openstack.common import wsgi


class JobsController(object):

    def __init__(self, db_api=None):
        self.db_api = db_api or qonos.db.get_api()

    def _get_request_params(self, request):
        params = {}
        params['limit'] = request.params.get('limit')
        params['marker'] = request.params.get('marker')
        return params

    def list(self, request):
        params = self._get_request_params(request)
        try:
            params = utils.get_pagination_limit(params)
        except exception.Invalid as e:
            raise webob.exc.HTTPBadRequest(explanation=str(e))
        try:
            jobs = self.db_api.job_get_all(params)
        except exception.NotFound:
            raise webob.exc.HTTPNotFound()

        for job in jobs:
            utils.serialize_datetimes(job)
            api_utils.serialize_job_metadata(job)
        return {'jobs': jobs}

    def create(self, request, body):
        if (body is None or body.get('job') is None or
                body['job'].get('schedule_id') is None):
            raise webob.exc.HTTPBadRequest()
        job = body['job']

        try:
            schedule = self.db_api.schedule_get_by_id(job['schedule_id'])
        except exception.NotFound:
            raise webob.exc.HTTPNotFound()

        values = {}
        values.update(job)
        values['tenant_id'] = schedule['tenant_id']
        values['action'] = schedule['action']
        values['status'] = 'queued'

        job_metadata = []
        for metadata in schedule['schedule_metadata']:
            job_metadata.append({
                    'key': metadata['key'],
                    'value': metadata['value']
                    })

        values['job_metadata'] = job_metadata

        job = self.db_api.job_create(values)
        utils.serialize_datetimes(job)
        api_utils.serialize_job_metadata(job)

        return {'job': job}

    def get(self, request, job_id):
        try:
            job = self.db_api.job_get_by_id(job_id)
        except exception.NotFound:
            raise webob.exc.HTTPNotFound
        utils.serialize_datetimes(job)
        api_utils.serialize_job_metadata(job)
        return {'job': job}

    def delete(self, request, job_id):
        try:
            self.db_api.job_delete(job_id)
        except exception.NotFound:
            msg = _('Job %s could not be found.') % job_id
            raise webob.exc.HTTPNotFound(explanation=msg)

    def update_status(self, request, job_id, body):
        status = body.get('status')
        if not status:
            raise webob.exc.HTTPBadRequest()

        values = {'status': status['status'].upper()}
        if 'timeout' in status:
            timeout = timeutils.parse_isotime(status['timeout'])
            values['timeout'] = timeutils.normalize_time(timeout)

        job = None
        try:
            job = self.db_api.job_update(job_id, values)
        except exception.NotFound:
            msg = _('Job %s could not be found.') % job_id
            raise webob.exc.HTTPNotFound(explanation=msg)

        if status['status'].upper() == 'ERROR':
            values = self._get_error_values(status, job)
            self.db_api.job_fault_create(values)

        return {'status': job['status'], 'timeout': job['timeout']}

    def _get_error_values(self, status, job):
        api_utils.serialize_job_metadata(job)
        job_metadata = job['metadata']
        values = {
            'job_id': job['id'],
            'action': job['action'],
            'schedule_id': job['schedule_id'],
            'tenant_id': job['tenant_id'],
            'worker_id': job['worker_id'] or 'UNASSIGNED',
            'job_metadata': str(job_metadata),
            }
        if 'error_message' in status:
            values['message'] = status['error_message']
        else:
            values['message'] = None

        return values


def create_resource():
    """QonoS resource factory method."""
    return wsgi.Resource(JobsController())
