# This file is part of the plan timetable generator, see LICENSE for details.

import datetime

from django.core.cache import cache
from django.core.management import call_command
from django.utils import timezone

from plan.common.models import Schedule, Semester, Student, Subscription
from plan.common.snapshot import get_schedule_snapshot
from plan.common.tests import BaseTestCase


class BackfillScheduleFreshnessCommandTestCase(BaseTestCase):
    fixtures = ["test_data.json", "test_user.json"]

    def test_backfill_creates_missing_rows_and_preserves_freshness_key(self):
        semester = Semester.objects.get(year=2009, type=Semester.SPRING)
        student = Student.objects.get(slug="adamcik")
        Schedule.objects.filter(semester_id=semester.id, student_id=student.id).delete()

        cache.clear()
        before = get_schedule_snapshot(semester, student.slug)
        before_key = before.freshness_key()

        call_command(
            "backfill_schedule_freshness",
            year=semester.year,
            type=semester.type,
        )

        row = Schedule.objects.get(semester_id=semester.id, student_id=student.id)
        self.assertEqual(0, row.version)

        cache.clear()
        after = get_schedule_snapshot(semester, student.slug)
        after_key = after.freshness_key()

        self.assertEqual(before_key, after_key)

    def test_backfill_dry_run_does_not_create_schedule_rows(self):
        semester = Semester.objects.get(year=2009, type=Semester.SPRING)
        student = Student.objects.get(slug="adamcik")

        Schedule.objects.filter(semester_id=semester.id, student_id=student.id).delete()

        call_command(
            "backfill_schedule_freshness",
            year=semester.year,
            type=semester.type,
            dry_run=True,
        )

        self.assertFalse(
            Schedule.objects.filter(
                semester_id=semester.id, student_id=student.id
            ).exists()
        )

    def test_backfill_includes_subscription_added_in_fallback_timestamp(self):
        semester = Semester.objects.get(year=2009, type=Semester.SPRING)
        student = Student.objects.get(slug="adamcik")

        Schedule.objects.filter(semester_id=semester.id, student_id=student.id).delete()

        older = timezone.make_aware(datetime.datetime(2009, 1, 1, 12, 0, 0))
        newer = timezone.make_aware(datetime.datetime(2010, 1, 1, 12, 0, 0))

        Subscription.objects.filter(
            student_id=student.id,
            course__semester_id=semester.id,
        ).update(last_modified=older, added=newer)

        call_command(
            "backfill_schedule_freshness",
            year=semester.year,
            type=semester.type,
        )

        row = Schedule.objects.get(semester_id=semester.id, student_id=student.id)
        self.assertEqual(int(newer.timestamp()), int(row.last_modified.timestamp()))
