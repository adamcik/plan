# This file is part of the plan timetable generator, see LICENSE for details.


from dataclasses import dataclass
from typing import Optional

from plan.common.models import Schedule as ScheduleModel, Semester, Student


@dataclass
class Schedule:
    semester: Semester
    student: Student
    last_modified: Optional[int] = None

    def bump_last_modified(self):
        if self.student.id is None:
            self.student = Student.objects.get(slug=self.student.slug)

        ScheduleModel.objects.update_or_create(
            semester_id=self.semester.id,
            student_id=self.student.id,
        )
