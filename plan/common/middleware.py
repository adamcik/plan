# pylint: disable-msg=W0232, C0111

from time import time
import sys
import re

from django.conf import settings
from django.core.cache import cache, get_cache
from django.views.debug import technical_500_response

dummy_cache = get_cache('plan.common.cache://?backend=dummy')
stats = re.compile(r'<!--\s*TIME\s*-->')

class InternalIpMiddleware(object):
    '''Middleware that adds IP to INTERNAL ips if user is superuser'''

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

class TimeViewMiddleware(object):
    '''Shows view timing info if cookie or get variable is set'''

    def process_view(self, request, view_func, view_args, view_kwargs):
        if 'time' not in request.COOKIES and 'time' not in request.GET:
            return None

        start = time()
        response = view_func(request, *view_args, **view_kwargs)
        total = time() - start

        total *= 1000

        response.content = stats.sub('%.2f ms' % total, response.content)

        return response

class CacheMiddleware(object):
    '''Attaches either a real or dummy cache instance to our request, cache
       instance should only be used for retrival'''

    def process_request(self, request):
        if 'no-cache' in request.GET or 'no-cache' in request.COOKIES:
            request.cache = dummy_cache
        else:
            request.cache = cache

        return None

class PlainContentMiddleware(object):
    def process_response(self, request, response):
        if 'plain' in request.GET:
            if 'Filename' in response:
                del response['Filename']
            if 'Content-Disposition' in response:
                del response['Content-Disposition']

            response['Content-Type'] = 'text/plain; charset=utf-8'

        return response
