import sys

from django.conf import settings
from django.views.debug import technical_500_response

from plan.common.utils import *

class InternalIpMiddleware:
    def process_request(self, request):
        if request.user.is_authenticated() and request.user.is_superuser:
            if request.META.get('REMOTE_ADDR') not in settings.INTERNAL_IPS:
                settings.INTERNAL_IPS += [request.META.get('REMOTE_ADDR')]
        return None

class TimingMiddleware:
    def process_request(self, request):
        request.timer = Timer()
        return None

    def process_response(self, request, response):
        if hasattr(request, 'timer'):
            request.timer.tick('Done')
        return response

class UserBasedExceptionMiddleware(object):
    def process_exception(self, request, exception):
        if request.user.is_superuser:
            return technical_500_response(request, *sys.exc_info())
