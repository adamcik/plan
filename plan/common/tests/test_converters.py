import datetime
from unittest import mock

from django.conf import settings as django_settings
from django.core.cache import caches
from django.db.models import Value
from django.utils import timezone

from plan.common.models import Schedule, Semester, Student, Subscription
from plan.common.snapshot import (
    delete_semester_freshness_cache,
    delete_schedule_snapshot_cache,
    get_schedule_snapshot,
    next_http_last_modified,
    semester_freshness_cache_key,
    schedule_snapshot_cache_key,
)


def test_to_python_populates_explicit_freshness_fields(
    serialized_schedule_data, cache_isolation
):
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

    assert schedule.version == 11
    assert schedule.semester_version == 7


def test_next_http_last_modified_advances_nullable_semester_timestamp(
    serialized_schedule_data, cache_isolation
):
    semester = Semester.objects.get(year=2009, type=Semester.SPRING)
    semester.last_modified = None
    semester.save(update_fields=["last_modified"])
    fixed_time = timezone.make_aware(datetime.datetime(2026, 1, 1, 12, 0, 0))

    with mock.patch("plan.common.snapshot.Now", return_value=Value(fixed_time)):
        Semester.objects.filter(id=semester.id).update(
            last_modified=next_http_last_modified("last_modified")
        )
        semester.refresh_from_db()
        first = int(semester.last_modified.timestamp())

        Semester.objects.filter(id=semester.id).update(
            last_modified=next_http_last_modified("last_modified")
        )
        semester.refresh_from_db()

    assert int(semester.last_modified.timestamp()) > first


def test_to_python_stores_split_freshness_entries_under_stable_keys(
    serialized_schedule_data, cache_isolation, settings
):
    settings.TIMETABLE_SNAPSHOT_CACHE_DISK_TTL = 7 * 24 * 60 * 60
    semester = Semester.objects.get(year=2009, type=Semester.SPRING)
    student = Student.objects.get(slug="adamcik")

    schedule = get_schedule_snapshot(semester, student.slug)
    schedule_key = schedule_snapshot_cache_key(semester, student.slug)
    semester_key = semester_freshness_cache_key(semester)

    cached_schedule = caches["default"].get(schedule_key)
    assert cached_schedule.student.slug == student.slug
    assert cached_schedule.version == schedule.version
    assert caches["default"].get(semester_key) == schedule.semester
    assert caches["disk"].get(schedule_key) == cached_schedule


def test_to_python_writes_split_freshness_entries_with_configured_ttls(
    serialized_schedule_data, cache_isolation
):
    semester = Semester.objects.get(year=2009, type=Semester.SPRING)
    student = Student.objects.get(slug="adamcik")
    schedule_key = schedule_snapshot_cache_key(semester, student.slug)
    semester_key = semester_freshness_cache_key(semester)

    with mock.patch.object(caches["default"], "set") as cache_set:
        get_schedule_snapshot(semester, student.slug)

    cache_set.assert_any_call(
        schedule_key,
        mock.ANY,
        django_settings.TIMETABLE_SNAPSHOT_CACHE_DEFAULT_TTL,
    )
    cache_set.assert_any_call(
        semester_key,
        mock.ANY,
        django_settings.TIMETABLE_SEMESTER_FRESHNESS_CACHE_DEFAULT_TTL,
    )


def test_to_python_cache_hit_does_not_query_db(
    serialized_schedule_data, cache_isolation, django_assert_num_queries
):
    semester = Semester.objects.get(year=2009, type=Semester.SPRING)
    student = Student.objects.get(slug="adamcik")

    get_schedule_snapshot(semester, student.slug)

    with django_assert_num_queries(0):
        cached = get_schedule_snapshot(semester, student.slug)

    assert cached.student.slug == student.slug
    assert cached.semester.id == semester.id


def test_semester_invalidation_refreshes_freshness_without_deleting_user_entry(
    serialized_schedule_data, cache_isolation
):
    semester = Semester.objects.get(year=2009, type=Semester.SPRING)
    student = Student.objects.get(slug="adamcik")
    schedule_key = schedule_snapshot_cache_key(semester, student.slug)

    before = get_schedule_snapshot(semester, student.slug)
    cached_schedule = caches["default"].get(schedule_key)
    Semester.objects.filter(id=semester.id).update(version=semester.version + 1)

    delete_semester_freshness_cache(semester)

    after = get_schedule_snapshot(semester, student.slug)

    assert after.freshness_key() != before.freshness_key()
    assert caches["default"].get(schedule_key) == cached_schedule


def test_to_python_happy_path_uses_single_schedule_lookup(
    serialized_schedule_data, cache_isolation, django_assert_num_queries
):
    semester = Semester.objects.get(year=2009, type=Semester.SPRING)
    student = Student.objects.get(slug="adamcik")
    Schedule.objects.get_or_create(semester_id=semester.id, student_id=student.id)

    with django_assert_num_queries(1):
        schedule = get_schedule_snapshot(semester, student.slug)

    assert schedule.student.slug == student.slug
    assert schedule.semester.id == semester.id


def test_to_python_happy_path_uses_max_of_schedule_and_semester_last_modified(
    serialized_schedule_data, cache_isolation
):
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

    assert schedule.last_modified == int(semester_ts.timestamp())


def test_to_python_legacy_fallback_when_versions_uninitialized(
    serialized_schedule_data, cache_isolation
):
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

    assert schedule.version == 0
    assert schedule.semester_version == 0
    assert schedule.last_modified is not None
    assert schedule.last_modified >= int(ts.timestamp())


def test_to_python_legacy_fallback_without_semester_last_modified_and_schedule_row(
    serialized_schedule_data, cache_isolation
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

    assert schedule.version == 0
    assert schedule.semester_version == 0
    assert schedule.last_modified is not None
    assert schedule.last_modified >= int(ts.timestamp())


def test_to_python_fallback_without_schedule_row_sets_dto_and_cache_key(
    serialized_schedule_data, cache_isolation, settings
):
    settings.TIMETABLE_SNAPSHOT_CACHE_DISK_TTL = 7 * 24 * 60 * 60
    semester = Semester.objects.get(year=2009, type=Semester.SPRING)
    student = Student.objects.get(slug="adamcik")

    semester.version = 3
    semester.last_modified = timezone.make_aware(datetime.datetime(2009, 1, 1, 9, 0, 0))
    semester.save(update_fields=["version", "last_modified"])

    Schedule.objects.filter(semester_id=semester.id, student_id=student.id).delete()

    ts = timezone.make_aware(datetime.datetime(2009, 1, 1, 10, 0, 0))
    Subscription.objects.filter(
        student_id=student.id,
        course__semester_id=semester.id,
    ).update(last_modified=ts)

    schedule = get_schedule_snapshot(semester, student.slug)
    key = schedule_snapshot_cache_key(semester, student.slug)

    assert schedule.version == 0
    assert schedule.semester_version == 3
    assert schedule.last_modified is not None
    assert schedule.last_modified >= int(ts.timestamp())
    assert schedule.last_modified >= int(semester.last_modified.timestamp())
    assert caches["default"].get(key).student.slug == student.slug
    assert caches["disk"].get(key).student.slug == student.slug


def test_to_python_disk_user_cache_hit_promotes_to_default(
    serialized_schedule_data, cache_isolation, settings, django_assert_num_queries
):
    settings.TIMETABLE_SNAPSHOT_CACHE_DISK_TTL = 7 * 24 * 60 * 60
    semester = Semester.objects.get(year=2009, type=Semester.SPRING)
    student = Student.objects.get(slug="adamcik")
    key = schedule_snapshot_cache_key(semester, student.slug)

    cached = get_schedule_snapshot(semester, student.slug)
    caches["default"].clear()

    with django_assert_num_queries(1):
        result = get_schedule_snapshot(semester, student.slug)

    assert result == cached
    assert caches["default"].get(key).student.slug == result.student.slug


def test_to_python_does_not_write_disk_layer_when_disabled(
    serialized_schedule_data, cache_isolation, settings
):
    settings.TIMETABLE_SNAPSHOT_CACHE_DISK_TTL = None
    semester = Semester.objects.get(year=2009, type=Semester.SPRING)
    student = Student.objects.get(slug="adamcik")
    key = schedule_snapshot_cache_key(semester, student.slug)

    schedule = get_schedule_snapshot(semester, student.slug)

    assert caches["default"].get(key).student.slug == schedule.student.slug
    assert caches["disk"].get(key) is None


def test_cached_none_is_invalidated_and_rebuilt(
    serialized_schedule_data, cache_isolation, caplog
):
    semester = Semester.objects.get(year=2009, type=Semester.SPRING)
    student = Student.objects.get(slug="adamcik")
    key = schedule_snapshot_cache_key(semester, student.slug)

    caches["default"].set(key, None, timeout=60)

    with caplog.at_level("WARNING", logger="plan.common.snapshot"):
        schedule = get_schedule_snapshot(semester, student.slug)

    assert key in caplog.text
    assert schedule is not None
    assert caches["default"].get(key).student.slug == schedule.student.slug


def test_delete_schedule_snapshot_cache_skips_missing_disk(
    serialized_schedule_data, cache_isolation, settings
):
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "snapshot-default-only",
        }
    }
    settings.TIMETABLE_SNAPSHOT_CACHE_DISK_TTL = None
    semester = Semester.objects.get(year=2009, type=Semester.SPRING)
    student = Student.objects.get(slug="adamcik")
    key = schedule_snapshot_cache_key(semester, student.slug)

    caches["default"].set(key, "dto", timeout=60)

    delete_schedule_snapshot_cache(semester, student.slug)

    assert caches["default"].get(key) is None
