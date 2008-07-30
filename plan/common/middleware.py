from django.conf import settings

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
        request.timer.tick('Done')
        return response
