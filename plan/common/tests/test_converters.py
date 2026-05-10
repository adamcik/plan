import datetime

from django.core.cache import cache
from django.utils import timezone

from plan.common.converters import ScheduleConverter
from plan.common.models import Schedule, Semester, Student, Subscription
from plan.common.tests import BaseTestCase


class ScheduleConverterTestCase(BaseTestCase):
    fixtures = ["test_data.json", "test_user.json"]

    def test_to_python_populates_explicit_freshness_fields(self):
        semester = Semester.objects.get(year=2009, type=Semester.SPRING)
        semester.version = 7
        semester.save(update_fields=["version"])

        student = Student.objects.get(slug="adamcik")
        schedule_row, _ = Schedule.objects.get_or_create(
            semester_id=semester.id,
            student_id=student.id,
        )
        schedule_row.version = 11
        schedule_row.save(update_fields=["version"])

        cache.clear()

        schedule = ScheduleConverter().to_python(
            f"{semester.year}/{semester.slug}/{student.slug}"
        )

        self.assertEqual(11, schedule.version)
        self.assertEqual(7, schedule.semester_version)

    def test_to_python_stores_schedule_dto_under_stable_key(self):
        semester = Semester.objects.get(year=2009, type=Semester.SPRING)
        student = Student.objects.get(slug="adamcik")

        cache.clear()
        converter = ScheduleConverter()
        path = f"{semester.year}/{semester.slug}/{student.slug}"

        schedule = converter.to_python(path)

        self.assertEqual(
            schedule,
            cache.get(f"schedule:{semester.year}-{semester.type}-{student.slug}"),
        )

    def test_to_python_legacy_fallback_when_versions_uninitialized(self):
        semester = Semester.objects.get(year=2009, type=Semester.SPRING)
        student = Student.objects.get(slug="adamcik")

        semester.version = 0
        semester.last_modified = None
        semester.save(update_fields=["version", "last_modified"])

        Schedule.objects.filter(semester_id=semester.id, student_id=student.id).delete()

        ts = timezone.make_aware(datetime.datetime(2009, 1, 1, 12, 0, 0))
        Subscription.objects.filter(
            student_id=student.id,
            course__semester_id=semester.id,
        ).update(last_modified=ts)

        cache.clear()

        schedule = ScheduleConverter().to_python(
            f"{semester.year}/{semester.slug}/{student.slug}"
        )

        self.assertEqual(0, schedule.version)
        self.assertEqual(0, schedule.semester_version)
        self.assertIsNotNone(schedule.last_modified)
        self.assertGreaterEqual(schedule.last_modified, int(ts.timestamp()))

    def test_to_python_legacy_fallback_without_semester_last_modified_and_schedule_row(
        self,
    ):
        semester = Semester.objects.get(year=2009, type=Semester.SPRING)
        student = Student.objects.get(slug="adamcik")

        semester.version = 0
        semester.last_modified = None
        semester.save(update_fields=["version", "last_modified"])

        Schedule.objects.filter(semester_id=semester.id, student_id=student.id).delete()

        ts = timezone.make_aware(datetime.datetime(2009, 1, 1, 13, 0, 0))
        Subscription.objects.filter(
            student_id=student.id,
            course__semester_id=semester.id,
        ).update(last_modified=ts)

        cache.clear()

        schedule = ScheduleConverter().to_python(
            f"{semester.year}/{semester.slug}/{student.slug}"
        )

        self.assertEqual(0, schedule.version)
        self.assertEqual(0, schedule.semester_version)
        self.assertIsNotNone(schedule.last_modified)
        self.assertGreaterEqual(schedule.last_modified, int(ts.timestamp()))
