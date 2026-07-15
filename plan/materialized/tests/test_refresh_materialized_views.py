# This file is part of the plan timetable generator, see LICENSE for details.

from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase

from plan.materialized.management.commands import refresh_materialized_views


class RefreshMaterializedViewsCommandTestCase(SimpleTestCase):
    @mock.patch.object(refresh_materialized_views, "monitor")
    @mock.patch.object(refresh_materialized_views, "MODELS", [])
    def test_reports_scheduled_refresh_to_sentry(self, monitor):
        call_command("refresh_materialized_views")

        monitor.assert_called_once_with(
            monitor_slug="materialized-views-refresh",
            monitor_config={
                "schedule": {"type": "interval", "value": 30, "unit": "minute"},
                "checkin_margin": 10,
                "max_runtime": 10,
            },
        )
