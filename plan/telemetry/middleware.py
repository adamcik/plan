import string
import time

import structlog
from django.http import HttpRequest, HttpResponse

logger: structlog.BoundLogger = structlog.get_logger("plan.http")
access_log_format = "{http.request.method} {http.route} {http.response.status_code}"


class AccessLogFormatter(string.Formatter):
    def get_field(self, field_name, args, kwargs):
        if field_name in kwargs:
            value = kwargs[field_name]
            return value if value is not None else "-", field_name
        return "{" + field_name + "}", field_name


class AccessLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        structlog.contextvars.clear_contextvars()
        start = time.perf_counter_ns()
        response = self.get_response(request)
        route = request.resolver_match.route if request.resolver_match else None
        content_length = response.headers.get("Content-Length")
        data = {
            "http.request.method": request.method,
            "http.response.status_code": response.status_code,
            "http.route": route,
            "network.protocol.version": request.META.get("SERVER_PROTOCOL"),
            "http.server.duration": (time.perf_counter_ns() - start) / 1e9,
            "http.response.header.content_length": content_length,
            "http.response.header.content_type": response.headers.get("Content-Type"),
            "http.response.header.cache_control": response.headers.get("Cache-Control"),
        }
        logger.info(AccessLogFormatter().format(access_log_format, **data), **data)
        structlog.contextvars.clear_contextvars()
        return response
