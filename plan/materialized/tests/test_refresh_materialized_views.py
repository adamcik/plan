# This file is part of the plan timetable generator, see LICENSE for details.

from unittest.mock import MagicMock

from django.core.management import call_command

from plan.materialized.management.commands import refresh_materialized_views


def test_reports_scheduled_refresh_to_sentry(monkeypatch):
    monitor = MagicMock()
    monkeypatch.setattr(refresh_materialized_views, "monitor", monitor)
    monkeypatch.setattr(refresh_materialized_views, "MODELS", [])

    call_command("refresh_materialized_views")

    monitor.assert_called_once_with(
        monitor_slug="materialized-views-refresh",
        monitor_config={
            "schedule": {"type": "interval", "value": 30, "unit": "minute"},
            "checkin_margin": 10,
            "max_runtime": 10,
        },
    )
