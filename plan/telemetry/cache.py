"""Django cache spans and metrics without recording cache values."""

import functools
import time
from collections.abc import Callable
from typing import Any

from django.core.cache.backends.base import BaseCache
from django.core.cache import caches
from opentelemetry import metrics, trace
from opentelemetry.trace import SpanKind, Status, StatusCode

_OPERATIONS = frozenset(
    {
        "get",
        "get_many",
        "set",
        "set_many",
        "add",
        "delete",
        "delete_many",
        "incr",
        "decr",
        "touch",
        "clear",
    }
)
_INSTRUMENTED_ATTRIBUTE = "_plan_telemetry_instrumented"
_instrumented = False
_original_getattribute: Callable[..., Any] | None = None

_tracer = trace.get_tracer("plan.telemetry.cache")
_meter = metrics.get_meter("plan.telemetry.cache")
_duration = _meter.create_histogram("django.cache.operation.duration", unit="s")
_operations = _meter.create_counter("django.cache.operations", unit="{operation}")


def instrument_cache() -> None:
    """Patch BaseCache once so every current and future backend is covered."""
    global _instrumented, _original_getattribute
    if _instrumented or getattr(BaseCache, _INSTRUMENTED_ATTRIBUTE, False):
        _instrumented = True
        return

    _original_getattribute = BaseCache.__getattribute__

    @functools.wraps(_original_getattribute)
    def getattribute(cache: BaseCache, name: str) -> Any:
        value = _original_getattribute(cache, name)
        if name not in _OPERATIONS or not callable(value):
            return value

        @functools.wraps(value)
        def instrumented(*args: Any, **kwargs: Any) -> Any:
            return _record(cache, name, value, args, kwargs)

        return instrumented

    BaseCache.__getattribute__ = getattribute
    setattr(BaseCache, _INSTRUMENTED_ATTRIBUTE, True)
    _instrumented = True
    original_create_connection = caches.create_connection

    @functools.wraps(original_create_connection)
    def create_connection(alias: str):
        cache = original_create_connection(alias)
        cache._plan_telemetry_alias = alias
        return cache

    caches.create_connection = create_connection


def _attributes(
    cache: BaseCache, operation: str, args: tuple[Any, ...]
) -> dict[str, str | int]:
    attributes: dict[str, str | int] = {
        "cache.alias": getattr(cache, "_plan_telemetry_alias", "unknown"),
        "cache.operation": operation,
        "cache.backend": type(cache).__name__,
    }
    if operation in {"get_many", "set_many", "delete_many"} and args:
        attributes["cache.batch.size"] = len(args[0])
    elif operation != "clear" and args:
        attributes["cache.key"] = str(args[0])
    if type(cache).__name__ == "PyLibMCCache":
        attributes["db.system"] = "memcached"
    return attributes


def _record(
    cache: BaseCache,
    operation: str,
    function: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> Any:
    attributes = _attributes(cache, operation, args)
    start = time.perf_counter()
    with _tracer.start_as_current_span(
        f"CACHE {operation.upper()}", kind=SpanKind.CLIENT, attributes=attributes
    ) as span:
        try:
            result, cache_hit = _call_cache_operation(operation, function, args, kwargs)
        except Exception as error:
            attributes["error.type"] = type(error).__name__
            span.record_exception(error)
            span.set_status(Status(StatusCode.ERROR, str(error)))
            raise
        else:
            if operation == "get":
                attributes["cache.hit"] = cache_hit
                span.set_attribute("cache.hit", cache_hit)
            elif operation == "get_many":
                attributes["cache.hit_count"] = len(result)
                attributes["cache.miss_count"] = attributes.get(
                    "cache.batch.size", 0
                ) - len(result)
            return result
        finally:
            elapsed = time.perf_counter() - start
            _duration.record(elapsed, attributes)
            _operations.add(1, attributes)


def _call_cache_operation(
    operation: str,
    function: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> tuple[Any, bool]:
    if operation != "get":
        return function(*args, **kwargs), False

    sentinel = object()
    default = kwargs.get("default", args[1] if len(args) > 1 else None)
    call_args = list(args)
    call_kwargs = dict(kwargs)
    if len(call_args) > 1:
        call_args[1] = sentinel
    else:
        call_kwargs["default"] = sentinel

    result = function(*call_args, **call_kwargs)
    if result is sentinel:
        return default, False
    return result, True
