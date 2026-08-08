# This file is part of the plan timetable generator, see LICENSE for details.

from datetime import timedelta

from django.core.management import base as management
from django.db.models import F
from django.utils import timezone

from plan.common.models import Schedule
from plan.common.snapshot import delete_schedule_snapshot_cache

MAX_FUTURE_LAST_MODIFIED = timedelta(minutes=1)


class Command(management.BaseCommand):
    help = "Repair future schedule freshness timestamps"

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Write repairs; omit to print affected rows without changing them",
        )

    def handle(self, **options):
        now = timezone.now()
        cutoff = now + MAX_FUTURE_LAST_MODIFIED
        candidates = list(
            Schedule.objects.filter(last_modified__gt=cutoff).select_related(
                "semester", "student"
            )
        )

        self.stdout.write(f"apply={options['apply']}")
        self.stdout.write(f"candidates={len(candidates)}")
        for row in candidates:
            self.stdout.write(
                f"schedule_id={row.id} semester={row.semester.year}/{row.semester.type} "
                f"student_slug={row.student.slug} "
                f"last_modified={row.last_modified.isoformat()} version={row.version}"
            )

        if not options["apply"]:
            return

        repaired = 0
        for row in candidates:
            updated = Schedule.objects.filter(
                id=row.id,
                last_modified__gt=cutoff,
            ).update(last_modified=now, version=F("version") + 1)
            if updated:
                delete_schedule_snapshot_cache(row.semester, row.student.slug)
                repaired += 1

        self.stdout.write(f"repaired={repaired}")
