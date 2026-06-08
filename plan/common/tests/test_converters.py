import datetime

from django.core.cache import caches
from django.test import override_settings
from django.utils import timezone

from plan.common.models import Schedule, Semester, Student, Subscription
from plan.common.snapshot import get_schedule_snapshot, schedule_snapshot_cache_key
from plan.common.tests import BaseTestCase


class ScheduleSnapshotTestCase(BaseTestCase):
    fixtures = ["test_data.json", "test_user.json"]

    def setUp(self):
        super().setUp()
        caches["default"].clear()
        caches["disk"].clear()

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

        schedule = get_schedule_snapshot(semester, student.slug)

        self.assertEqual(11, schedule.version)
        self.assertEqual(7, schedule.semester_version)

    @override_settings(TIMETABLE_SNAPSHOT_CACHE_DISK_TTL=7 * 24 * 60 * 60)
    def test_to_python_stores_schedule_dto_under_stable_key(self):
        semester = Semester.objects.get(year=2009, type=Semester.SPRING)
        student = Student.objects.get(slug="adamcik")

        schedule = get_schedule_snapshot(semester, student.slug)
        key = schedule_snapshot_cache_key(semester, student.slug)

        self.assertEqual(
            schedule,
            caches["default"].get(key),
        )
        self.assertEqual(
            schedule,
            caches["disk"].get(key),
        )

    def test_to_python_cache_hit_does_not_query_db(self):
        semester = Semester.objects.get(year=2009, type=Semester.SPRING)
        student = Student.objects.get(slug="adamcik")

        get_schedule_snapshot(semester, student.slug)

        with self.assertNumQueries(0):
            cached = get_schedule_snapshot(semester, student.slug)

        self.assertEqual(student.slug, cached.student.slug)
        self.assertEqual(semester.id, cached.semester.id)

    def test_to_python_happy_path_uses_single_schedule_lookup(self):
        semester = Semester.objects.get(year=2009, type=Semester.SPRING)
        student = Student.objects.get(slug="adamcik")
        Schedule.objects.get_or_create(semester_id=semester.id, student_id=student.id)

        with self.assertNumQueries(1):
            schedule = get_schedule_snapshot(semester, student.slug)

        self.assertEqual(student.slug, schedule.student.slug)
        self.assertEqual(semester.id, schedule.semester.id)

    def test_to_python_happy_path_uses_max_of_schedule_and_semester_last_modified(self):
        semester = Semester.objects.get(year=2009, type=Semester.SPRING)
        student = Student.objects.get(slug="adamcik")
        schedule_row, _ = Schedule.objects.get_or_create(
            semester_id=semester.id,
            student_id=student.id,
        )

        schedule_ts = timezone.make_aware(datetime.datetime(2009, 1, 1, 11, 0, 0))
        semester_ts = timezone.make_aware(datetime.datetime(2009, 1, 1, 12, 0, 0))
        Schedule.objects.filter(id=schedule_row.id).update(last_modified=schedule_ts)
        Semester.objects.filter(id=semester.id).update(last_modified=semester_ts)

        schedule = get_schedule_snapshot(semester, student.slug)

        self.assertEqual(int(semester_ts.timestamp()), schedule.last_modified)

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

        schedule = get_schedule_snapshot(semester, student.slug)

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

        schedule = get_schedule_snapshot(semester, student.slug)

        self.assertEqual(0, schedule.version)
        self.assertEqual(0, schedule.semester_version)
        self.assertIsNotNone(schedule.last_modified)
        self.assertGreaterEqual(schedule.last_modified, int(ts.timestamp()))

    @override_settings(TIMETABLE_SNAPSHOT_CACHE_DISK_TTL=7 * 24 * 60 * 60)
    def test_to_python_fallback_without_schedule_row_sets_dto_and_cache_key(self):
        semester = Semester.objects.get(year=2009, type=Semester.SPRING)
        student = Student.objects.get(slug="adamcik")

        semester.version = 3
        semester.last_modified = timezone.make_aware(
            datetime.datetime(2009, 1, 1, 9, 0, 0)
        )
        semester.save(update_fields=["version", "last_modified"])

        Schedule.objects.filter(semester_id=semester.id, student_id=student.id).delete()

        ts = timezone.make_aware(datetime.datetime(2009, 1, 1, 10, 0, 0))
        Subscription.objects.filter(
            student_id=student.id,
            course__semester_id=semester.id,
        ).update(last_modified=ts)

        schedule = get_schedule_snapshot(semester, student.slug)
        key = schedule_snapshot_cache_key(semester, student.slug)

        self.assertEqual(0, schedule.version)
        self.assertEqual(3, schedule.semester_version)
        self.assertIsNotNone(schedule.last_modified)
        self.assertGreaterEqual(schedule.last_modified, int(ts.timestamp()))
        self.assertGreaterEqual(
            schedule.last_modified,
            int(semester.last_modified.timestamp()),
        )
        self.assertEqual(
            schedule,
            caches["default"].get(key),
        )
        self.assertEqual(
            schedule,
            caches["disk"].get(key),
        )

    @override_settings(TIMETABLE_SNAPSHOT_CACHE_DISK_TTL=7 * 24 * 60 * 60)
    def test_to_python_disk_cache_hit_does_not_query_db_and_promotes_to_default(self):
        semester = Semester.objects.get(year=2009, type=Semester.SPRING)
        student = Student.objects.get(slug="adamcik")
        key = schedule_snapshot_cache_key(semester, student.slug)

        cached = get_schedule_snapshot(semester, student.slug)
        caches["default"].clear()

        with self.assertNumQueries(0):
            result = get_schedule_snapshot(semester, student.slug)

        self.assertEqual(cached, result)
        self.assertEqual(result, caches["default"].get(key))

    @override_settings(TIMETABLE_SNAPSHOT_CACHE_DISK_TTL=None)
    def test_to_python_does_not_write_disk_layer_when_disabled(self):
        semester = Semester.objects.get(year=2009, type=Semester.SPRING)
        student = Student.objects.get(slug="adamcik")
        key = schedule_snapshot_cache_key(semester, student.slug)

        schedule = get_schedule_snapshot(semester, student.slug)

        self.assertEqual(schedule, caches["default"].get(key))
        self.assertIsNone(caches["disk"].get(key))
