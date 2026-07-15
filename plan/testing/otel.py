"""OpenTelemetry test doubles and process-global state reset."""

import opentelemetry.metrics._internal
import opentelemetry.trace
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.util._once import Once

__all__ = ["InMemoryMetricReader", "InMemorySpanExporter", "reset_otel_once"]


def reset_otel_once() -> None:
    """Reset OTel provider singleton guards for test isolation."""
    opentelemetry.trace._TRACER_PROVIDER_SET_ONCE = Once()
    opentelemetry.metrics._internal._METER_PROVIDER_SET_ONCE = Once()
