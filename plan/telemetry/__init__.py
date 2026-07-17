"""Application-owned OpenTelemetry setup."""

import importlib.metadata
import importlib.util
from dataclasses import dataclass
from typing import Literal

from django.conf import settings as django_settings
from opentelemetry import metrics, propagate, trace
from opentelemetry.baggage.propagation import W3CBaggagePropagator
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.django import DjangoInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.propagators import (
    TraceResponsePropagator,
    set_global_response_propagator,
)
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.system_metrics import SystemMetricsInstrumentor
from opentelemetry.propagators.composite import CompositePropagator
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from plan.telemetry.cache import instrument_cache
from plan.telemetry.logging import configure as configure_logging
from plan.telemetry.templates import instrument_templates

Components = Literal["tracing", "metrics"]
_initialized = False


@dataclass(frozen=True)
class TelemetrySettings:
    components: frozenset[Components]
    endpoint: str
    trace_sample_rate: float
    export_timeout_seconds: float
    metric_export_interval_seconds: float


def settings_from_environment() -> TelemetrySettings:
    from plan.settings.env import Settings

    env = Settings()
    return TelemetrySettings(
        components=frozenset(
            component.value for component in env.plan_telemetry_components
        ),
        endpoint=env.otel_exporter_otlp_endpoint,
        trace_sample_rate=env.otel_trace_sample_rate,
        export_timeout_seconds=env.otel_export_timeout_seconds,
        metric_export_interval_seconds=env.otel_metric_export_interval_seconds,
    )


def _otlp_endpoint(endpoint: str, signal: str) -> str:
    return f"{endpoint.rstrip('/')}/v1/{signal}"


def _url_without_query(url: str) -> str:
    return url.partition("?")[0]


def _django_response_hook(span, request, response) -> None:
    if not span or not span.is_recording():
        return
    match = request.resolver_match
    if match and match.view_name:
        span.set_attribute("django.route.name", match.view_name)
        span.update_name(f"{request.method} {match.view_name}")


def init(settings: TelemetrySettings | None = None) -> None:
    """Configure providers and instrumentation once per process."""
    global _initialized
    if _initialized:
        return

    settings = settings or settings_from_environment()
    if not settings.components:
        _initialized = True
        return

    resource = Resource.create(django_settings.OTEL_RESOURCE_ATTRIBUTES)
    configure_logging()
    if "tracing" in settings.components:
        provider = TracerProvider(
            resource=resource,
            sampler=TraceIdRatioBased(settings.trace_sample_rate),
        )
        provider.add_span_processor(
            BatchSpanProcessor(
                OTLPSpanExporter(
                    endpoint=_otlp_endpoint(settings.endpoint, "traces"),
                    timeout=settings.export_timeout_seconds,
                )
            )
        )
        _add_sentry_processor(provider)
        trace.set_tracer_provider(provider)
        propagators = [TraceContextTextMapPropagator(), W3CBaggagePropagator()]
        if _sentry_otel_available():
            from sentry_sdk.integrations.opentelemetry.propagator import (
                SentryPropagator,
            )

            propagators.append(SentryPropagator())
        propagate.set_global_textmap(CompositePropagator(propagators))
        set_global_response_propagator(TraceResponsePropagator())

    if "metrics" in settings.components:
        reader = PeriodicExportingMetricReader(
            OTLPMetricExporter(
                endpoint=_otlp_endpoint(settings.endpoint, "metrics"),
                timeout=settings.export_timeout_seconds,
            ),
            export_interval_millis=int(settings.metric_export_interval_seconds * 1000),
        )
        metrics.set_meter_provider(
            MeterProvider(resource=resource, metric_readers=[reader])
        )

    _instrument(settings)
    _initialized = True


def _instrument(settings: TelemetrySettings) -> None:
    excluded_urls = "/static/.*|/__debug__/.*|/metrics"
    DjangoInstrumentor().instrument(
        excluded_urls=excluded_urls,
        response_hook=_django_response_hook,
    )
    RequestsInstrumentor().instrument(url_filter=_url_without_query)
    Psycopg2Instrumentor().instrument(enable_commenter=False)
    LoggingInstrumentor().instrument(set_logging_format=False)
    if "tracing" in settings.components:
        instrument_templates()
    if "metrics" in settings.components:
        SystemMetricsInstrumentor().instrument()
    instrument_cache()


def _sentry_otel_available() -> bool:
    return importlib.util.find_spec("sentry_sdk.integrations.opentelemetry") is not None


def _add_sentry_processor(provider: TracerProvider) -> None:
    if not _sentry_otel_available():
        return
    from sentry_sdk.integrations.opentelemetry.span_processor import SentrySpanProcessor

    provider.add_span_processor(SentrySpanProcessor())


def version() -> str:
    try:
        return importlib.metadata.version("plan")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"
