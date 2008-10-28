# pylint: disable-msg=W0232, C0111

import sys

from django.conf import settings
from django.views.debug import technical_500_response

from plan.common.utils import Timer

class InternalIpMiddleware:
    '''Middleware that adds IP to INTERNAL ips if user is superuser'''
    def process_request(self, request):
        if request.user.is_authenticated() and request.user.is_superuser:
            if request.META.get('REMOTE_ADDR') not in settings.INTERNAL_IPS:
                settings.INTERNAL_IPS += [request.META.get('REMOTE_ADDR')]
        return None

class UserBasedExceptionMiddleware(object):
    '''Exception middleware that gives super users technical_500_response'''
    def process_exception(self, request, exception):
        if request.user.is_superuser:
            return technical_500_response(request, *sys.exc_info())
