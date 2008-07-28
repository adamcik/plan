from django.conf import settings

class InternalIpMiddleware:
    def process_request(self, request):
        if request.user.is_authenticated() and request.user.is_superuser:
            if request.META.get('REMOTE_ADDR') not in settings.INTERNAL_IPS:
                settings.INTERNAL_IPS += [request.META.get('REMOTE_ADDR')]
        return None
