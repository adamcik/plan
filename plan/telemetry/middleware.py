import time

import structlog
from django.http import HttpRequest, HttpResponse

logger: structlog.BoundLogger = structlog.get_logger("plan.http")


class AccessLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        start = time.perf_counter()
        response = self.get_response(request)
        route = request.resolver_match.route if request.resolver_match else None
        logger.info(
            f"{request.method} {route or '-'} {response.status_code}",
            **{
                "http.request.method": request.method,
                "http.response.status_code": response.status_code,
                "http.route": route,
                "http.server.duration": time.perf_counter() - start,
            },
        )
        return response
