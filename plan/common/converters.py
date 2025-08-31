# This file is part of the plan timetable generator, see LICENSE for details.


import re

from django.core.cache import cache
from django.db.models.aggregates import Max
from django.http import Http404

from plan.common.models import Semester, Student, Subscription
from plan.common.schedule import Schedule


class ScheduleConverter:
    regex = r"(\d{4})/([a-z]+)/([a-zA-Z0-9-_]{1,50})"
    _pattern = re.compile(regex)

    def to_python(self, value: str) -> Schedule:
        match = self._pattern.match(value)
        year, semester_type, slug = match.groups()

        key = f"modified-{year}-{semester_type}-{slug}"
        result = cache.get(key)
        if result:
            return result

        try:
            semester = Semester.objects.get(
                year=year,
                type=semester_type,
            )
        except Semester.DoesNotExist:
            raise Http404(f"Semester does not exist, year={year}, type={semester_type}")

        try:
            student = Student.objects.get(slug=slug)
        except Student.DoesNotExist:
            return Schedule(
                student_slug=slug,
                semester=semester,
                student=None,
            )

        # NOTE: Knowning the exact student_id makes this query much faster.
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
        last_modified = max([0] + [int(agg.timestamp()) for agg in qs.values() if agg])

        result = Schedule(
            student_slug=slug,
            semester=semester,
            student=student,
            last_modified=last_modified,
        )

        cache.set(key, result, timeout=60)
        return result

    def to_url(self, schedule: Schedule) -> str:
        return "/".join(
            str(v)
            for v in [
                schedule.semester.year,
                Semester.localize(schedule.semester.type),
                schedule.student_slug,
            ]
        )


class WeekNumberConverter:
    regex = r"\d{1,2}"

    def to_python(self, value: str) -> int:
        try:
            week_num = int(value)
        except ValueError:
            raise Http404(f"Invalid week number format: {value}")

        if 1 <= week_num <= 53:
            return week_num
        else:
            raise Http404(f"Week number out of valid range (1-53): {value}")

    def to_url(self, value: int) -> str:
        if not isinstance(value, int):
            raise ValueError(
                f"Expected an integer week number, got {type(value).__name__}."
            )

        if not (1 <= value <= 53):
            raise ValueError(f"Week number out of valid range (1-53): {value}")

        return str(value)


# --- Base58 Encoding/Decoding Utility (unchanged) ---
_BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_BASE58_BASE = len(_BASE58_ALPHABET)


def _encode_int_to_base58(num: int) -> str:
    if not isinstance(num, int) or num < 0:
        raise ValueError("Input must be a non-negative integer.")
    if num == 0:
        return _BASE58_ALPHABET[0]
    res = []
    while num > 0:
        num, rem = divmod(num, _BASE58_BASE)
        res.append(_BASE58_ALPHABET[rem])
    return "".join(reversed(res))


def _decode_base58_to_int(s: str) -> int:  # ... (as previously defined)
    num = 0
    for char in s:
        try:
            char_value = _BASE58_ALPHABET.index(char)
        except ValueError:
            raise ValueError(f"Invalid Base58 character: '{char}' in string '{s}'")
        num = num * _BASE58_BASE + char_value
    return num


class Base58Converter:
    regex = r"[" + re.escape(_BASE58_ALPHABET) + "]+"

    def to_python(self, value: str) -> int:
        try:
            return _decode_base58_to_int(value)
        except ValueError as e:
            raise Http404(f"Invalid ID: {value}. Details: {e}")

    def to_url(self, value: int) -> str:
        try:
            return _encode_int_to_base58(value)
        except ValueError as e:
            raise ValueError(
                f"Cannot encode value to Base58 for URL: {value}. Details: {e}"
            )
