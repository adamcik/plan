# This file is part of the plan timetable generator, see LICENSE for details.

from dataclasses import dataclass
from typing import Optional

from django.core.cache import cache
from django.db.models import F
from django.db.models.aggregates import Max
from django.http import Http404
from django.utils import timezone

from plan.common.models import (
    Schedule as ScheduleModel,
    Semester,
    Student,
    Subscription,
)


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

    def bump_last_modified(self):
        if self.student.id is None:
            self.student = Student.objects.get(slug=self.student.slug)

        row, created = ScheduleModel.objects.get_or_create(
            semester_id=self.semester.id,
            student_id=self.student.id,
        )

        if created:
            ScheduleModel.objects.filter(id=row.id).update(version=1)
            self.version = 1
            return

        ScheduleModel.objects.filter(id=row.id).update(
            version=F("version") + 1,
            last_modified=timezone.now(),
        )
        row.refresh_from_db(fields=["version"])
        self.version = row.version


def get_schedule_snapshot(semester: Semester, student_slug: str) -> ScheduleSnapshot:
    key = f"schedule:{semester.year}-{semester.type}-{student_slug}"
    result = cache.get(key)
    if result:
        return result

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

    cache.set(key, result, timeout=60)
    return result


def _build_schedule_snapshot_legacy_fallback(
    *,
    semester_year: int,
    semester_type: str,
    student_slug: str,
) -> ScheduleSnapshot:
    try:
        semester = Semester.objects.get(year=semester_year, type=semester_type)
    except Semester.DoesNotExist:
        raise Http404(
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
