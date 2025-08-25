# This file is part of the plan timetable generator, see LICENSE for details.

import time

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from plan.materialized.models import SemesterAnalytics, TopCourses, SubscriptionsCount

MODELS = [SemesterAnalytics, TopCourses, SubscriptionsCount]


class Command(BaseCommand):
    help = "Refreshes all specified materialized views."

    def handle(self, *args, **options):
        self.stdout.write(f"Starting refresh of {len(MODELS)} materialized view(s).\n")

        success = 0
        with connection.cursor() as cursor:
            for model in MODELS:
                table = model._meta.db_table
                self.stdout.write(f"  Refreshing {self.style.SQL_TABLE(table)}")

                try:
                    start_time = time.time()
                    with transaction.atomic():
                        cursor.execute(
                            # NOTE: Normally we should never use f-string for
                            # queries, but this is OK as we are using a static
                            # string from our DB model.
                            f"REFRESH MATERIALIZED VIEW CONCURRENTLY {table}"
                        )
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

        msg = f"{success} of {len(MODELS)} updates succedded."
        if success != len(MODELS):
            self.stderr.write(self.style.WARNING(msg))
            raise CommandError(msg)
        else:
            self.stdout.write(self.style.SUCCESS(msg))
