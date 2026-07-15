import string
import time
from typing import Any
from urllib.parse import urlsplit

import structlog
from django.http import HttpRequest, HttpResponse
from django.utils.translation import get_language

logger: structlog.BoundLogger = structlog.get_logger("plan.http")
access_log_format = '{client.address} - "{http.request.method} {url.path} {network.protocol.version}" {http.response.status_code}'


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
        structlog.contextvars.bind_contextvars(language=get_language())
        start = time.perf_counter_ns()
        response = self.get_response(request)
        data = {
            **get_request_info(request, time.perf_counter_ns() - start),
            **get_response_info(response),
        }
        logger.info(AccessLogFormatter().format(access_log_format, **data), **data)
        structlog.contextvars.clear_contextvars()
        return response


def get_request_info(request: HttpRequest, duration_ns: int) -> dict[str, Any]:
    url = request.build_absolute_uri()
    parts = urlsplit(url)
    return {
        "client.address": request.META.get("REMOTE_ADDR"),
        "http.server.duration": duration_ns / 1e9,
        "http.request.method": request.method,
        "http.request.body.size": request.META.get("CONTENT_LENGTH"),
        "http.route": request.resolver_match.route if request.resolver_match else None,
        "network.protocol.version": request.META.get("SERVER_PROTOCOL"),
        "server.address": request.get_host(),
        "url.full": url,
        "url.path": request.path,
        "url.query": parts.query,
        "url.scheme": request.scheme,
        "user_agent.original": request.headers.get("User-Agent"),
        "http.request.header.content_type": request.content_type,
        "http.request.header.content_length": request.headers.get("Content-Length"),
    }


def get_response_info(response: HttpResponse) -> dict[str, Any]:
    content_length = response.headers.get("Content-Length")
    response_size = (
        int(content_length)
        if content_length is not None and content_length.isdigit()
        else None
    )
    if response_size is None and not response.streaming:
        response_size = len(response.content)
    return {
        "http.response.body.size": response_size,
        "http.response.status_code": response.status_code,
        "http.response.header.content_length": content_length,
        "http.response.header.content_type": response.headers.get("Content-Type"),
        "http.response.header.cache_control": response.headers.get("Cache-Control"),
        "http.response.header.x_cache": response.headers.get("X-Cache"),
    }
