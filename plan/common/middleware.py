# pylint: disable-msg=W0232, C0111

import sys
import re
import logging
from time import time

from django.conf import settings
from django.views.debug import technical_500_response
from django.http import HttpResponseServerError

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

class CacheMiddleware(object):
    '''Attaches either a real or dummy cache instance to our request, cache
       instance should only be used for retrival'''

    def __init__(self):
        self.logger = logging.getLogger('plan.middleware.cache')

    def process_request(self, request):
        request.use_cache = True

        if self._ignore_cache(request):
            self.logger.debug('Ignoring cache')
            request.use_cache = False

        return None

    def _ignore_cache(self, request):
        return (
            (request.user.is_authenticated() and
             request.META.get('HTTP_CACHE_CONTROL', '').lower() == 'no-cache') or
            'no-cache' in request.GET or
            'no-cache' in request.COOKIES
        )

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
