# This file is part of the plan timetable generator, see LICENSE for details.

import datetime
from dataclasses import dataclass

from django.core.management import base as management
from django.db import connection
from django.db import transaction
from django.db.models.aggregates import Max

from plan.common.models import (
    Schedule as ScheduleModel,
    Semester,
    Student,
)
from plan.common.schedule import Schedule


@dataclass
class Candidate:
    student_id: int
    student_slug: str
    fallback_last_modified: int | None
    pre_key: str


class Command(management.BaseCommand):
    help = "Backfill missing schedule rows while preserving freshness keys"

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--year", action="store", dest="year", type=int, required=True
        )
        parser.add_argument(
            "--type",
            action="store",
            dest="type",
            choices=list(dict(Semester.SEMESTER_TYPES).keys()),
            required=True,
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            dest="dry_run",
            help="Do not write changes",
        )

    def handle(self, **options):
        semester = self._load_semester(options["year"], options["type"])
        counters = self._run_for_semester(semester, options["dry_run"])

        self.stdout.write(f"semester={semester.year}/{semester.type}")
        self.stdout.write(f"dry_run={options['dry_run']}")
        self.stdout.write(f"candidates={counters['candidates']}")
        self.stdout.write(f"missing_before={counters['missing_before']}")
        self.stdout.write(f"created={counters['created']}")
        self.stdout.write(f"skipped_no_timestamp={counters['skipped_no_timestamp']}")
        self.stdout.write(f"verified={counters['verified']}")

    def _load_semester(self, year: int, semester_type: str) -> Semester:
        try:
            return Semester.objects.get(year=year, type=semester_type)
        except Semester.DoesNotExist as e:
            raise management.CommandError(
                f"Semester not found: year={year} type={semester_type}"
            ) from e

    def _run_for_semester(self, semester: Semester, dry_run: bool) -> dict[str, int]:
        candidates = self._build_missing_candidates(semester)
        missing_with_timestamp = [
            c for c in candidates if c.fallback_last_modified is not None
        ]
        skipped_no_timestamp = len(candidates) - len(missing_with_timestamp)

        counters = {
            "candidates": len(candidates),
            "missing_before": len(candidates),
            "created": 0,
            "skipped_no_timestamp": skipped_no_timestamp,
            "verified": 0,
        }

        if dry_run:
            counters["verified"] = len(missing_with_timestamp)
            return counters

        with transaction.atomic():
            rows = []
            for candidate in missing_with_timestamp:
                rows.append(
                    (
                        semester.id,
                        candidate.student_id,
                        datetime.datetime.fromtimestamp(
                            candidate.fallback_last_modified,
                            tz=datetime.timezone.utc,
                        ),
                    )
                )
            self._insert_rows(rows)
            counters["created"] = len(rows)

            created_rows = {
                row.student_id: row
                for row in ScheduleModel.objects.filter(
                    semester_id=semester.id,
                    student_id__in=[c.student_id for c in missing_with_timestamp],
                )
            }

            for candidate in missing_with_timestamp:
                row = created_rows.get(candidate.student_id)
                if not row:
                    raise management.CommandError(
                        "Missing created schedule row for "
                        f"semester_id={semester.id} student_id={candidate.student_id}"
                    )

                post_last_modified = (
                    int(row.last_modified.timestamp()) if row.last_modified else None
                )
                post_key = Schedule(
                    semester=semester,
                    student=Student(
                        id=candidate.student_id,
                        slug=candidate.student_slug,
                    ),
                    version=row.version,
                    last_modified=post_last_modified,
                    semester_version=semester.version,
                ).freshness_key()

                if candidate.pre_key != post_key:
                    raise management.CommandError(
                        "Freshness key mismatch for "
                        f"semester_id={semester.id} student_id={candidate.student_id}: "
                        f"before={candidate.pre_key} after={post_key}"
                    )

            counters["verified"] = len(missing_with_timestamp)

        return counters

    def _build_missing_candidates(self, semester: Semester) -> list[Candidate]:
        rows = (
            Student.objects.filter(subscription__course__semester_id=semester.id)
            .exclude(schedule__semester_id=semester.id)
            .values("id", "slug")
            .annotate(
                subscription_added=Max("subscription__added"),
                subscription_last_modified=Max("subscription__last_modified"),
                courses_last_modified=Max("subscription__course__last_modified"),
                lectures_last_modified=Max(
                    "subscription__course__lecture__last_modified"
                ),
                rooms_last_modified=Max(
                    "subscription__course__lecture__rooms__last_modified"
                ),
                exams_last_modified=Max("subscription__course__exam__last_modified"),
                semester_last_modified=Max(
                    "subscription__course__semester__last_modified"
                ),
            )
            .order_by("id")
        )

        missing_candidates = []
        for row in rows:
            timestamps = []
            for key in (
                "subscription_added",
                "subscription_last_modified",
                "courses_last_modified",
                "lectures_last_modified",
                "rooms_last_modified",
                "exams_last_modified",
                "semester_last_modified",
            ):
                value = row.get(key)
                if value:
                    timestamps.append(int(value.timestamp()))

            fallback_last_modified = max(timestamps) if timestamps else None
            pre_key = Schedule(
                semester=semester,
                student=Student(id=row["id"], slug=row["slug"]),
                version=0,
                last_modified=fallback_last_modified,
                semester_version=semester.version,
            ).freshness_key()

            missing_candidates.append(
                Candidate(
                    student_id=row["id"],
                    student_slug=row["slug"],
                    fallback_last_modified=fallback_last_modified,
                    pre_key=pre_key,
                )
            )

        return missing_candidates

    def _insert_rows(self, rows: list[tuple[int, int, datetime.datetime]]):
        """Insert backfill rows with exact timestamps.

        We intentionally bypass ORM writes here because `Schedule.last_modified`
        uses `auto_now=True`. ORM create/save paths can overwrite provided
        timestamps, which would break freshness-key parity checks.
        """
        if not rows:
            return

        params = [
            (semester_id, student_id, last_modified, 0)
            for semester_id, student_id, last_modified in rows
        ]

        with connection.cursor() as cursor:
            cursor.executemany(
                "INSERT INTO common_schedule "
                "(semester_id, student_id, last_modified, version) "
                "VALUES (%s, %s, %s, %s)",
                params,
            )
