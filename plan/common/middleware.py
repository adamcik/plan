# Copyright 2008, 2009 Thomas Kongevold Adamcik
# 2009 IME Faculty Norwegian University of Science and Technology

# This file is part of Plan.
#
# Plan is free software: you can redistribute it and/or modify
# it under the terms of the Affero GNU General Public License as
# published by the Free Software Foundation, either version 3 of
# the License, or (at your option) any later version.
#
# Plan is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# Affero GNU General Public License for more details.
#
# You should have received a copy of the Affero GNU General Public
# License along with Plan.  If not, see <http://www.gnu.org/licenses/>.

import sys
import logging

from django.conf import settings
from django.views.debug import technical_500_response


class InternalIpMiddleware(object):
    '''Middleware that adds IP to INTERNAL ips if user is superuser'''

    # FIXME munging settings during runtime is somewhat questionable...
    def process_request(self, request):
        if request.user.is_authenticated() and request.user.is_superuser:
            if request.META.get('REMOTE_ADDR') not in settings.INTERNAL_IPS:
                settings.INTERNAL_IPS = list(settings.INTERNAL_IPS) + [request.META.get('REMOTE_ADDR')]
        return None


class UserBasedExceptionMiddleware(object):
    '''Exception middleware that gives super users technical_500_response'''

    def process_exception(self, request, exception):
        if request.user.is_superuser:
            return technical_500_response(request, *sys.exc_info())


class PlainContentMiddleware(object):
    def __init__(self):
        self.logger = logging.getLogger('plan.middleware.plain')

    def process_response(self, request, response):
        if 'plain' in request.GET:
            self.logger.debug('Forcing text/plain')

            if 'Filename' in response:
                del response['Filename']
            if 'Content-Disposition' in response:
                del response['Content-Disposition']

            response['Content-Type'] = 'text/plain; charset=utf-8'

        return response
