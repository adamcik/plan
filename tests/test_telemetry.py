import os
import subprocess
import sys
from unittest import mock

from django.core.cache import caches
from django.test import SimpleTestCase
from opentelemetry import metrics, trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

from plan.telemetry import TelemetrySettings, _django_response_hook
from plan.telemetry.cache import instrument_cache
from plan.telemetry import resources
from plan.telemetry.resources import resource_attributes
from plan.testing.otel import InMemorySpanExporter, reset_otel_once
from plan.settings.env import TelemetryComponent
from plan.settings.runtime import _sentry_otel_options


class TelemetryTestCase(SimpleTestCase):
    def test_django_response_hook_records_route_name(self):
        span = mock.Mock()
        span.is_recording.return_value = True
        request = mock.Mock()
        request.resolver_match.view_name = "schedule"

        _django_response_hook(span, request, mock.Mock())

        span.set_attribute.assert_called_once_with("django.route.name", "schedule")

    def test_wsgi_logs_without_telemetry(self):
        environment = os.environ.copy()
        environment.pop("PLAN_TELEMETRY_COMPONENTS", None)
        script = "from plan.wsgi import application; import logging; logging.getLogger('plan.test').info('standard log probe')"

        result = subprocess.run(
            [sys.executable, "-c", script],
            env=environment,
            capture_output=True,
            text=True,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("standard log probe", result.stderr)

    def test_wsgi_bootstraps_after_django_settings_are_complete(self):
        environment = os.environ | {
            "PLAN_TELEMETRY_COMPONENTS": "tracing",
            "DJANGO_ALLOWED_HOSTS": "testserver",
        }
        script = "from plan.wsgi import application; from django.conf import settings; from django.test import Client; import logging; assert settings.ROOT_URLCONF == 'plan.urls'; logging.getLogger('plan.test').info('telemetry log probe'); assert Client().get('/robots.txt?student=secret').status_code == 200"

        result = subprocess.run(
            [sys.executable, "-c", script],
            env=environment,
            capture_output=True,
            text=True,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn('"event": "telemetry log probe"', result.stderr)
        self.assertIn('"http.route": "^robots.txt"', result.stderr)
        self.assertIn('"language": "en"', result.stderr)
        self.assertIn("GET /robots.txt HTTP/1.1", result.stderr)
        self.assertIn("student=secret", result.stderr)

    def test_sentry_uses_otel_instrumenter_only_for_otel_tracing(self):
        self.assertEqual({}, _sentry_otel_options(set()))
        self.assertEqual(
            {"instrumenter": "otel"},
            _sentry_otel_options({TelemetryComponent.TRACING}),
        )

    def test_resource_attributes_include_service_identity(self):
        settings = TelemetrySettings(
            components=frozenset({"tracing", "metrics"}),
            endpoint="http://collector:4318",
            service_name="test-plan",
            service_version="1.2.3",
            deployment_environment="testing",
            service_instance_id="test-1",
            vcs_revision="abc1234",
            trace_sample_rate=1,
            export_timeout_seconds=1,
            metric_export_interval_seconds=60,
        )

        attributes = resource_attributes(settings)

        self.assertEqual("test-plan", attributes["service.name"])
        self.assertEqual("1.2.3", attributes["service.version"])
        self.assertEqual("testing", attributes["deployment.environment.name"])
        self.assertEqual("test-1", attributes["service.instance.id"])
        self.assertEqual("abc1234", attributes["vcs.revision"])

    @mock.patch.object(resources.os, "getpid", return_value=2002)
    @mock.patch.object(resources.socket, "gethostname", return_value="delta")
    def test_resource_attributes_derives_instance_id_per_worker(
        self, gethostname, getpid
    ):
        settings = TelemetrySettings(
            components=frozenset(),
            endpoint="http://collector:4318",
            service_name="test-plan",
            service_version="1.2.3",
            deployment_environment="testing",
            service_instance_id=None,
            vcs_revision=None,
            trace_sample_rate=1,
            export_timeout_seconds=1,
            metric_export_interval_seconds=60,
        )

        attributes = resource_attributes(settings)

        self.assertEqual("delta-testing-2002", attributes["service.instance.id"])
        gethostname.assert_called_once_with()
        self.assertEqual(2, getpid.call_count)

    def test_cache_span_records_cached_none_as_a_hit_without_key_or_value(self):
        reset_otel_once()
        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        metrics.set_meter_provider(
            MeterProvider(metric_readers=[InMemoryMetricReader()])
        )
        instrument_cache()

        cache = caches["default"]
        cache._plan_telemetry_alias = "default"
        cache.set("student-123", None)
        self.assertIsNone(cache.get("student-123"))

        spans = exporter.get_finished_spans()
        get_span = next(span for span in spans if span.name == "cache get")
        self.assertEqual("default", get_span.attributes["cache.alias"])
        self.assertTrue(get_span.attributes["cache.hit"])
        self.assertNotIn("cache.key", get_span.attributes)
        self.assertNotIn("cache.value", get_span.attributes)
