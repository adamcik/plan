import json
import os
import subprocess
import sys
from unittest import mock

import pytest
from django.core.cache import caches
from django.template import Context, Engine, engines
from opentelemetry import metrics, trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

from plan.settings.env import TelemetryComponent
from plan.settings.runtime import MIDDLEWARE, _sentry_otel_options
from plan.telemetry import _django_response_hook
from plan.telemetry import cache as telemetry_cache
from plan.telemetry.cache import instrument_cache
from plan.telemetry.templates import instrument_templates
from plan.testing.otel import InMemorySpanExporter, reset_otel_once


@pytest.fixture
def exporter():
    reset_otel_once()
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    metrics.set_meter_provider(MeterProvider(metric_readers=[InMemoryMetricReader()]))
    return exporter


def test_django_response_hook_records_route_name():
    span = mock.Mock()
    span.is_recording.return_value = True
    request = mock.Mock()
    request.method = "GET"
    request.resolver_match.view_name = "schedule"

    _django_response_hook(span, request, mock.Mock())

    span.set_attribute.assert_called_once_with("django.route.name", "schedule")
    span.update_name.assert_called_once_with("GET schedule")


def test_access_log_middleware_wraps_the_full_django_stack():
    assert MIDDLEWARE[0] == "plan.telemetry.middleware.AccessLogMiddleware"


def test_wsgi_logs_without_telemetry():
    environment = os.environ.copy()
    environment.pop("PLAN_TELEMETRY_COMPONENTS", None)
    script = "from plan.wsgi import application; import logging; logging.getLogger('plan.test').info('standard log probe')"

    result = subprocess.run(
        [sys.executable, "-c", script],
        env=environment,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "standard log probe" in result.stderr


def test_wsgi_bootstraps_after_django_settings_are_complete():
    environment = os.environ | {
        "PLAN_TELEMETRY_COMPONENTS": "tracing",
        "DJANGO_ALLOWED_HOSTS": "testserver",
        "OTEL_SERVICE_NAME": "test-plan",
        "OTEL_SERVICE_INSTANCE_ID": "test-plan-1",
        "OTEL_DEPLOYMENT_ENVIRONMENT": "testing",
    }
    script = "from plan.wsgi import application; from django.conf import settings; from django.test import Client; import logging; assert settings.ROOT_URLCONF == 'plan.urls'; logging.getLogger('plan.test').info('telemetry log probe'); assert Client().get('/robots.txt?student=secret').status_code == 200"

    result = subprocess.run(
        [sys.executable, "-c", script],
        env=environment,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert '"event": "telemetry log probe"' in result.stderr
    assert '"http.route": "^robots.txt"' in result.stderr
    assert '"language": "en"' in result.stderr
    assert "GET /robots.txt HTTP/1.1" in result.stderr
    assert "student=secret" in result.stderr
    telemetry_log = next(
        json.loads(line)
        for line in result.stderr.splitlines()
        if '"event": "telemetry log probe"' in line
    )
    assert telemetry_log["service.name"] == "test-plan"
    assert telemetry_log["service.instance.id"] == "test-plan-1"
    assert telemetry_log["deployment.environment.name"] == "testing"


def test_sentry_uses_otel_instrumenter_only_for_otel_tracing():
    assert _sentry_otel_options(set()) == {}
    assert _sentry_otel_options({TelemetryComponent.TRACING}) == {
        "instrumenter": "otel"
    }


def test_cache_span_records_cached_none_as_a_hit_without_key_or_value(
    exporter, cache_isolation
):
    instrument_cache()

    cache = caches["default"]
    cache._plan_telemetry_alias = "default"
    cache.set("student-123", None)
    assert cache.get("student-123") is None

    spans = exporter.get_finished_spans()
    get_span = next(span for span in spans if span.name == "CACHE GET")
    assert get_span.attributes["cache.alias"] == "default"
    assert get_span.attributes["cache.hit"]
    assert "cache.key" not in get_span.attributes
    assert "cache.value" not in get_span.attributes

    telemetry_cache._instrumented = False
    instrument_cache()

    exporter.clear()
    assert cache.get("student-123") is None

    spans = exporter.get_finished_spans()
    assert len([span for span in spans if span.name == "CACHE GET"]) == 1


def test_template_rendering_creates_a_span(exporter):
    instrument_templates()

    engines["django"].from_string("Hello {{ name }}").render({"name": "Plan"})
    engine = Engine(
        loaders=[
            (
                "django.template.loaders.locmem.Loader",
                {
                    "parent.html": '{% include "child.html" %}',
                    "child.html": "Hello {{ name }}",
                },
            )
        ]
    )
    engine.get_template("parent.html").render(Context({"name": "Plan"}))

    spans = exporter.get_finished_spans()
    span = next(span for span in spans if span.name == "TEMPLATE <string>")
    assert span.attributes["django.template.name"] == "<string>"
    assert {span.name for span in spans} == {
        "TEMPLATE <string>",
        "TEMPLATE parent.html",
        "TEMPLATE child.html",
    }
