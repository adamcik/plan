# This file is part of the plan timetable generator, see LICENSE for details.

from dataclasses import dataclass
from datetime import time
from enum import IntEnum

type WeekNumber = int


class Weekday(IntEnum):
    MONDAY = 0
    TUESDAY = 1
    WEDNESDAY = 2
    THURSDAY = 3
    FRIDAY = 4
    SATURDAY = 5
    SUNDAY = 6


@dataclass(frozen=True, slots=True)
class LectureData:
    lecture_id: int

    title: str | None
    summary: str | None
    stream: str | None

    day: Weekday
    start: time
    end: time

    week_numbers: tuple[WeekNumber, ...]

    alias: str | None
    exclude: bool

    course_id: int
    course_code: str
    course_name: str

    type_id: int | None
    type_code: str | None
    type_name: str | None
    type_optional: bool
