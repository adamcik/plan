# This file is part of the plan timetable generator, see LICENSE for details.

import time

from django.core.management.base import BaseCommand, CommandError
from sentry_sdk.crons import monitor
from opentelemetry import trace

from plan.materialized.models import SemesterAnalytics, SubscriptionsCount, TopCourses

MODELS = [SemesterAnalytics, TopCourses, SubscriptionsCount]

MONITOR_CONFIG = {
    "schedule": {"type": "interval", "value": 30, "unit": "minute"},
    "checkin_margin": 10,
    "max_runtime": 10,
}
tracer = trace.get_tracer("plan.materialized")


class Command(BaseCommand):
    help = "Refreshes all specified materialized views."

    def handle(self, *args, **options):
        with tracer.start_as_current_span("MATERIALIZED VIEWS REFRESH"):
            with monitor(
                monitor_slug="materialized-views-refresh", monitor_config=MONITOR_CONFIG
            ):
                self.refresh_views()

    def refresh_views(self):
        self.stdout.write(f"Starting refresh of {len(MODELS)} materialized view(s).\n")

        success = 0
        for cls in MODELS:
            self.stdout.write(f"  Refreshing {cls._meta.verbose_name}")

            try:
                start_time = time.time()
                cls.refresh_view()
                end_time = time.time()

                success += 1

                self.stdout.write(
                    self.style.SUCCESS(
                        f"  Finished in {end_time - start_time:.2f} seconds."
                    )
                )
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"  Failed to refresh: {e}"))
            finally:
                self.stdout.write("\n")

        msg = f"{success} of {len(MODELS)} updates succeeded."
        if success != len(MODELS):
            self.stderr.write(self.style.WARNING(msg))
            raise CommandError(msg)
        else:
            self.stdout.write(self.style.SUCCESS(msg))
