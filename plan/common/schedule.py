# This file is part of the plan timetable generator, see LICENSE for details.


from dataclasses import dataclass
from typing import Optional

from plan.common.models import Semester, Student


@dataclass
class Schedule:
    student_slug: str
    semester: Semester
    student: Optional[Student] = None
    last_modified: Optional[int] = None

    def key(self):
        return "-".join(
            str(v)
            for v in [
                self.semester.year,
                self.semester.type,
                self.student_slug,
                self.last_modified,
            ]
        )
