# This file is part of the plan timetable generator, see LICENSE for details.

import logging
from datetime import timedelta
from dataclasses import dataclass
from django.conf import settings
from django.core.cache import caches
from django.db.models import DateTimeField, ExpressionWrapper, F, Value
from django.db.models.aggregates import Max
from django.db.models.functions import Coalesce, Greatest, Now, TruncSecond

from plan.common.cache import MultiCache
from plan.common.models import (
    Schedule as ScheduleModel,
    Semester,
    Student,
    Subscription,
)

logger = logging.getLogger(__name__)


class ScheduleSnapshotNotFound(Exception):
    pass


@dataclass
class ScheduleSnapshot:
    """Render snapshot of a student's schedule and freshness metadata.

    This is intentionally separate from the ORM Schedule model. It carries only
    the fields needed by view/cache code (semester, student, freshness/version)
    and acts as the stable value cached by `get_schedule_snapshot(...)`.
    """

    semester: Semester
    student: Student
    last_modified: int | None = None
    version: int = 0
    semester_version: int = 0

    def freshness_key(self) -> str:
        return (
            f"{self.semester.year}-{self.semester.type}:"
            f"{self.semester_version}-{self.student.slug}:"
            f"{self.version}-{self.last_modified or 0}"
        )


@dataclass
class _ScheduleFreshness:
    student: Student
    last_modified: int | None = None
    version: int = 0


def schedule_snapshot_cache_key(semester: Semester, student_slug: str) -> str:
    return f"schedule:v2:{semester.year}-{semester.type}-{student_slug}"


def semester_freshness_cache_key(semester: Semester) -> str:
    return f"semester:{semester.year}-{semester.type}"


def delete_schedule_snapshot_cache(semester: Semester, student_slug: str) -> None:
    key = schedule_snapshot_cache_key(semester, student_slug)
    caches["default"].delete(key)
    if "disk" in settings.CACHES:
        caches["disk"].delete(key)


def delete_semester_freshness_cache(semester: Semester) -> None:
    caches["default"].delete(semester_freshness_cache_key(semester))


def next_http_last_modified(field: str):
    """Return a timestamp newer than the prior HTTP-date second."""
    now = Now()
    previous = Coalesce(F(field), now)
    next_second = ExpressionWrapper(
        TruncSecond(previous) + Value(timedelta(seconds=1)),
        output_field=DateTimeField(),
    )
    return Greatest(now, next_second)


def _schedule_snapshot_cache_for_config(
    default_ttl: int | None,
    disk_ttl: int | None,
) -> MultiCache[ScheduleSnapshot]:
    if default_ttl is None:
        raise ValueError("TIMETABLE_SNAPSHOT_CACHE_DEFAULT_TTL must not be None")

    if disk_ttl is not None:
        return MultiCache[ScheduleSnapshot](default=default_ttl, disk=disk_ttl)

    return MultiCache[ScheduleSnapshot](default=default_ttl)


def _schedule_snapshot_cache() -> MultiCache[_ScheduleFreshness]:
    return _schedule_snapshot_cache_for_config(
        settings.TIMETABLE_SNAPSHOT_CACHE_DEFAULT_TTL,
        settings.TIMETABLE_SNAPSHOT_CACHE_DISK_TTL,
    )


def _semester_freshness_cache() -> MultiCache[Semester]:
    ttl = settings.TIMETABLE_SEMESTER_FRESHNESS_CACHE_DEFAULT_TTL
    if ttl is None:
        raise ValueError(
            "TIMETABLE_SEMESTER_FRESHNESS_CACHE_DEFAULT_TTL must not be None"
        )
    return MultiCache[Semester](default=ttl)


def get_schedule_snapshot(semester: Semester, student_slug: str) -> ScheduleSnapshot:
    def get_cached_value(cache: MultiCache, key: str, cache_name: str):
        result = cache.get(key)
        if result.hit and result.value is None:
            logger.warning(
                "Cached %s unexpectedly None for key %s; invalidating and rebuilding",
                cache_name,
                key,
            )
            cache.delete(key)
            return cache.get(key)
        return result

    schedule_key = schedule_snapshot_cache_key(semester, student_slug)
    snapshot_cache = _schedule_snapshot_cache()
    cached_schedule = get_cached_value(
        snapshot_cache, schedule_key, "schedule snapshot"
    )

    semester_key = semester_freshness_cache_key(semester)
    semester_cache = _semester_freshness_cache()
    cached_semester = get_cached_value(
        semester_cache, semester_key, "semester freshness"
    )

    if (
        cached_semester.hit
        and cached_semester.value is not None
        and cached_schedule.hit
        and cached_schedule.value is not None
    ):
        return _compose_snapshot(cached_semester.value, cached_schedule.value)

    if cached_schedule.hit and cached_schedule.value is not None:
        cached_semester_value = Semester.objects.get(
            year=semester.year, type=semester.type
        )
        semester_cache.set(semester_key, cached_semester_value)
        return _compose_snapshot(cached_semester_value, cached_schedule.value)

    try:
        schedule_row = ScheduleModel.objects.select_related("semester", "student").get(
            semester__year=semester.year,
            semester__type=semester.type,
            student__slug=student_slug,
        )
    except ScheduleModel.DoesNotExist:
        try:
            cached_semester_value = Semester.objects.get(
                year=semester.year, type=semester.type
            )
        except Semester.DoesNotExist:
            raise ScheduleSnapshotNotFound(
                f"Could not find semester: year={semester.year} type={semester.type}"
            )
        cached_schedule_value = _build_schedule_freshness_legacy_fallback(
            semester=cached_semester_value,
            student_slug=student_slug,
        )
    else:
        cached_semester_value = schedule_row.semester
        cached_schedule_value = _ScheduleFreshness(
            student=schedule_row.student,
            last_modified=(
                int(schedule_row.last_modified.timestamp())
                if schedule_row.last_modified
                else None
            ),
            version=schedule_row.version,
        )

    if not cached_semester.hit:
        semester_cache.set(semester_key, cached_semester_value)
    if not cached_schedule.hit:
        snapshot_cache.set(schedule_key, cached_schedule_value)
    return _compose_snapshot(cached_semester_value, cached_schedule_value)


def bump_snapshot(snapshot: ScheduleSnapshot) -> None:
    if snapshot.student.id is None:
        snapshot.student = Student.objects.get(slug=snapshot.student.slug)

    row, _ = ScheduleModel.objects.get_or_create(
        semester_id=snapshot.semester.id,
        student_id=snapshot.student.id,
    )

    ScheduleModel.objects.filter(id=row.id).update(
        version=F("version") + 1,
        last_modified=next_http_last_modified("last_modified"),
    )
    row.refresh_from_db(fields=["version"])
    snapshot.version = row.version


def _compose_snapshot(
    semester: Semester, schedule: _ScheduleFreshness
) -> ScheduleSnapshot:
    timestamps = [schedule.last_modified] if schedule.last_modified else []
    if semester.last_modified:
        timestamps.append(int(semester.last_modified.timestamp()))
    return ScheduleSnapshot(
        semester=semester,
        student=schedule.student,
        last_modified=max(timestamps) if timestamps else None,
        version=schedule.version,
        semester_version=semester.version,
    )


def _build_schedule_freshness_legacy_fallback(
    *,
    semester: Semester,
    student_slug: str,
) -> _ScheduleFreshness:
    try:
        student = Student.objects.get(slug=student_slug)
    except Student.DoesNotExist:
        return _ScheduleFreshness(student=Student(slug=student_slug))

    qs = Subscription.objects.filter(
        course__semester_id=semester.id,
        student_id=student.id,
    ).aggregate(
        subscription_added=Max("added"),
        subscription_last_modified=Max("last_modified"),
        courses_last_modified=Max("course__last_modified"),
        lectures_last_modified=Max("course__lecture__last_modified"),
        rooms_last_modified=Max("course__lecture__rooms__last_modified"),
        exams_last_modified=Max("course__exam__last_modified"),
    )

    timestamps = [int(agg.timestamp()) for agg in qs.values() if agg]
    last_modified = max([0] + timestamps)

    return _ScheduleFreshness(
        student=student,
        last_modified=last_modified or None,
        version=0,
    )
