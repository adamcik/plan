# This file is part of the plan timetable generator, see LICENSE for details.


from dataclasses import dataclass
from typing import Optional

from django.db.models import F
from django.utils import timezone

from plan.common.models import Schedule as ScheduleModel, Semester, Student


@dataclass
class Schedule:
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
