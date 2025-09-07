# This file is part of the plan timetable generator, see LICENSE for details.


from dataclasses import dataclass
from typing import Optional

from plan.common.models import Semester, Student


@dataclass
class Schedule:
    semester: Semester
    student: Student
    last_modified: Optional[int] = None
