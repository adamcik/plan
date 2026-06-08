# This file is part of the plan timetable generator, see LICENSE for details.

from functools import cache
from dataclasses import dataclass
from typing import Optional

from django.conf import settings
from django.core.cache import caches
from django.db.models import F
from django.db.models.aggregates import Max
from django.utils import timezone

from plan.common.cache import MultiCache
from plan.common.models import (
    Schedule as ScheduleModel,
    Semester,
    Student,
    Subscription,
)


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
    last_modified: Optional[int] = None
    version: int = 0
    semester_version: int = 0

    def freshness_key(self) -> str:
        return (
            f"{self.semester.year}-{self.semester.type}:"
            f"{self.semester_version}-{self.student.slug}:"
            f"{self.version}-{self.last_modified or 0}"
        )


def schedule_snapshot_cache_key(semester: Semester, student_slug: str) -> str:
    return f"schedule:{semester.year}-{semester.type}-{student_slug}"


def delete_schedule_snapshot_cache(semester: Semester, student_slug: str) -> None:
    key = schedule_snapshot_cache_key(semester, student_slug)
    caches["default"].delete(key)
    caches["disk"].delete(key)


@cache
def _schedule_snapshot_cache_for_config(
    default_ttl: int | None,
    disk_ttl: int | None,
) -> MultiCache[ScheduleSnapshot]:
    if default_ttl is None:
        raise ValueError("TIMETABLE_SNAPSHOT_CACHE_DEFAULT_TTL must not be None")

    if disk_ttl is not None:
        return MultiCache[ScheduleSnapshot](default=default_ttl, disk=disk_ttl)

    return MultiCache[ScheduleSnapshot](default=default_ttl)


def _schedule_snapshot_cache() -> MultiCache[ScheduleSnapshot]:
    return _schedule_snapshot_cache_for_config(
        settings.TIMETABLE_SNAPSHOT_CACHE_DEFAULT_TTL,
        settings.TIMETABLE_SNAPSHOT_CACHE_DISK_TTL,
    )


def get_schedule_snapshot(semester: Semester, student_slug: str) -> ScheduleSnapshot:
    key = schedule_snapshot_cache_key(semester, student_slug)
    result = _schedule_snapshot_cache().get(key)
    if result.hit:
        if result.value is None:
            raise ValueError(
                f"Cached schedule snapshot unexpectedly None for key {key}"
            )
        return result.value

    try:
        schedule_row = ScheduleModel.objects.select_related("semester", "student").get(
            semester__year=semester.year,
            semester__type=semester.type,
            student__slug=student_slug,
        )
    except ScheduleModel.DoesNotExist:
        result = _build_schedule_snapshot_legacy_fallback(
            semester_year=semester.year,
            semester_type=semester.type,
            student_slug=student_slug,
        )
    else:
        timestamps = []
        if schedule_row.semester.last_modified:
            timestamps.append(int(schedule_row.semester.last_modified.timestamp()))
        if schedule_row.last_modified:
            timestamps.append(int(schedule_row.last_modified.timestamp()))

        result = ScheduleSnapshot(
            semester=schedule_row.semester,
            student=schedule_row.student,
            last_modified=max(timestamps) if timestamps else None,
            version=schedule_row.version,
            semester_version=schedule_row.semester.version,
        )

    _schedule_snapshot_cache().set(key, result)
    return result


def bump_snapshot(snapshot: ScheduleSnapshot) -> None:
    if snapshot.student.id is None:
        snapshot.student = Student.objects.get(slug=snapshot.student.slug)

    row, created = ScheduleModel.objects.get_or_create(
        semester_id=snapshot.semester.id,
        student_id=snapshot.student.id,
    )

    if created:
        ScheduleModel.objects.filter(id=row.id).update(version=1)
        snapshot.version = 1
        return

    ScheduleModel.objects.filter(id=row.id).update(
        version=F("version") + 1,
        last_modified=timezone.now(),
    )
    row.refresh_from_db(fields=["version"])
    snapshot.version = row.version


def _build_schedule_snapshot_legacy_fallback(
    *,
    semester_year: int,
    semester_type: str,
    student_slug: str,
) -> ScheduleSnapshot:
    try:
        semester = Semester.objects.get(year=semester_year, type=semester_type)
    except Semester.DoesNotExist:
        raise ScheduleSnapshotNotFound(
            f"Could not find semester: year={semester_year} type={semester_type}"
        )

    try:
        student = Student.objects.get(slug=student_slug)
    except Student.DoesNotExist:
        return ScheduleSnapshot(
            semester=semester,
            student=Student(slug=student_slug),
        )

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
    if semester.last_modified:
        timestamps.append(int(semester.last_modified.timestamp()))

    last_modified = max([0] + timestamps)

    return ScheduleSnapshot(
        semester=semester,
        student=student,
        last_modified=last_modified or None,
        version=0,
        semester_version=semester.version,
    )
