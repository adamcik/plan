"""Django cache spans and metrics without recording cache values."""

import functools
import time
from collections.abc import Callable
from enum import StrEnum
from typing import Any, Literal, NotRequired, TypeVar, TypedDict, cast

from django.core.cache.backends.base import BaseCache
from django.core.cache import caches
from opentelemetry import metrics, trace
from opentelemetry.trace import SpanKind, Status, StatusCode


class CacheOperation(StrEnum):
    GET = "get"
    GET_MANY = "get_many"
    SET = "set"
    SET_MANY = "set_many"
    ADD = "add"
    DELETE = "delete"
    DELETE_MANY = "delete_many"
    INCR = "incr"
    DECR = "decr"
    TOUCH = "touch"
    CLEAR = "clear"


CacheBackend = Literal["file", "memcached", "memory", "other"]
T = TypeVar("T")


# Dotted OpenTelemetry attribute names require __annotations__, not class fields.
# Metric labels must remain bounded to avoid creating unbounded time series.
class MetricAttributes(TypedDict):
    __annotations__ = {
        "cache.alias": str,
        "cache.backend": CacheBackend,
        "cache.operation": CacheOperation,
        "cache.hit": NotRequired[bool],
    }


class SpanAttributes(MetricAttributes):
    __annotations__ = {
        "cache.batch.size": NotRequired[int],
        "cache.key": NotRequired[str],
        "cache.hit_count": NotRequired[int],
        "cache.miss_count": NotRequired[int],
        "db.system": NotRequired[str],
        "error.type": NotRequired[str],
    }


_INSTRUMENTED_ATTRIBUTE = "_plan_telemetry_instrumented"
_instrumented = False
_original_getattribute: Callable[..., Any] | None = None

_tracer = trace.get_tracer("plan.telemetry.cache")
_meter = metrics.get_meter("plan.telemetry.cache")
_duration = _meter.create_histogram("django.cache.operation.duration", unit="s")
_operations = _meter.create_counter("django.cache.operations", unit="{operation}")


def _cache_operation(name: str) -> CacheOperation | None:
    try:
        return CacheOperation(name)
    except ValueError:
        return None


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
        operation = _cache_operation(name)
        if operation is None or not callable(value):
            return value

        @functools.wraps(value)
        def instrumented(*args: Any, **kwargs: Any) -> Any:
            return _record(cache, operation, value, args, kwargs)

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


def _metric_backend(cache: BaseCache) -> CacheBackend:
    match type(cache).__name__:
        case "PyLibMCCache":
            return "memcached"
        case "FileBasedCache":
            return "file"
        case "LocMemCache":
            return "memory"
        case _:
            return "other"


def _metric_attributes(cache: BaseCache, operation: CacheOperation) -> MetricAttributes:
    """Return the bounded cache dimensions approved for metrics."""
    return {
        "cache.alias": str(getattr(cache, "_plan_telemetry_alias", "unknown")),
        "cache.backend": _metric_backend(cache),
        "cache.operation": operation,
    }


def _span_attributes(
    cache: BaseCache,
    operation: CacheOperation,
    args: tuple[Any, ...],
    metric_attributes: MetricAttributes,
) -> SpanAttributes:
    """Add trace-only cache details to the bounded metric dimensions."""
    span_attributes = cast(SpanAttributes, metric_attributes.copy())
    if operation in {"get_many", "set_many", "delete_many"} and args:
        span_attributes["cache.batch.size"] = len(args[0])
    elif operation != "clear" and args:
        span_attributes["cache.key"] = str(args[0])
    if type(cache).__name__ == "PyLibMCCache":
        span_attributes["db.system"] = "memcached"
    return span_attributes


def _record(
    cache: BaseCache,
    operation: CacheOperation,
    function: Callable[..., T],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> T:
    metric_attributes = _metric_attributes(cache, operation)
    span_attributes = _span_attributes(cache, operation, args, metric_attributes)
    start = time.perf_counter()
    with _tracer.start_as_current_span(
        f"CACHE {operation.upper()}", kind=SpanKind.CLIENT, attributes=span_attributes
    ) as span:
        try:
            result, cache_hit = _call_cache_operation(operation, function, args, kwargs)
        except Exception as error:
            span_attributes["error.type"] = type(error).__name__
            span.record_exception(error)
            span.set_status(Status(StatusCode.ERROR, str(error)))
            raise
        else:
            if operation == "get":
                span_attributes["cache.hit"] = cache_hit
                metric_attributes["cache.hit"] = cache_hit
                span.set_attribute("cache.hit", cache_hit)
            elif operation == "get_many":
                span_attributes["cache.hit_count"] = len(result)
                span_attributes["cache.miss_count"] = span_attributes.get(
                    "cache.batch.size", 0
                ) - len(result)
            return result
        finally:
            elapsed = time.perf_counter() - start
            _duration.record(elapsed, metric_attributes)
            _operations.add(1, metric_attributes)


def _call_cache_operation(
    operation: CacheOperation,
    function: Callable[..., T],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> tuple[T, bool]:
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
