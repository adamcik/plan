# This file is part of the plan timetable generator, see LICENSE for details.


import re

from django.conf import settings
from django.core.cache import cache
from django.db.models.aggregates import Max
from django.http import Http404
from django.utils import translation

from plan.common.models import (
    Schedule as ScheduleModel,
    Semester,
    Student,
    Subscription,
)
from plan.common.schedule import Schedule


class SemesterConverter:
    regex: str = r"(\d{4})/([a-z]+)"

    def __init__(self):
        self._pattern: re.Pattern[str] = re.compile(self.regex)
        self._types = {}

        for lang, _ in settings.LANGUAGES:
            with translation.override(lang):
                for value, slug in Semester.SEMESTER_SLUG.items():
                    self._types[str(slug)] = value

    def to_python(self, value: str) -> Semester:
        match = self._pattern.match(value)
        if not match:
            raise RuntimeError(
                f"Matching regexp failed, this should never happen: {value}"
            )
        return Semester(
            year=int(match.group(1)),
            type=self._types[match.group(2)],
        )

    def to_url(self, semester: Semester) -> str:
        return f"{semester.year}/{semester.slug}"


class StudentConverter:
    regex: str = r"([a-zA-Z0-9-_]{1,50})"

    def to_python(self, value: str) -> str:
        return value

    def to_url(self, slug: str) -> str:
        return slug


class ScheduleConverter:
    regex: str = r"(\d{4}/[a-z]+)/([a-zA-Z0-9-_]{1,50})"

    _pattern: re.Pattern[str] = re.compile(regex)

    _semester_converter = SemesterConverter()
    _student_converter = StudentConverter()

    def to_python(self, value: str) -> Schedule:
        match = self._pattern.match(value)
        if not match:
            raise RuntimeError(
                f"Matching regexp failed, this should never happen: {value}"
            )

        semester = self._semester_converter.to_python(match.group(1))
        student_slug = self._student_converter.to_python(match.group(2))

        key = f"schedule:{semester.year}-{semester.type}-{student_slug}"
        result = cache.get(key)
        if result:
            return result

        try:
            schedule_row = ScheduleModel.objects.select_related(
                "semester", "student"
            ).get(
                semester__year=semester.year,
                semester__type=semester.type,
                student__slug=student_slug,
            )
        except ScheduleModel.DoesNotExist:
            result = self._build_schedule_legacy_fallback(
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

            result = Schedule(
                semester=schedule_row.semester,
                student=schedule_row.student,
                last_modified=max(timestamps) if timestamps else None,
                version=schedule_row.version,
                semester_version=schedule_row.semester.version,
            )

        cache.set(key, result, timeout=60)
        return result

    def to_url(self, schedule: Schedule) -> str:
        return "/".join(
            (
                self._semester_converter.to_url(schedule.semester),
                self._student_converter.to_url(schedule.student.slug),
            )
        )

    def _build_schedule_legacy_fallback(
        self,
        *,
        semester_year: int,
        semester_type: str,
        student_slug: str,
    ) -> Schedule:
        try:
            semester = Semester.objects.get(year=semester_year, type=semester_type)
        except Semester.DoesNotExist:
            raise Http404(
                f"Could not find semester: year={semester_year} type={semester_type}"
            )

        try:
            student = Student.objects.get(slug=student_slug)
        except Student.DoesNotExist:
            return Schedule(
                semester=semester,
                student=Student(slug=student_slug),
            )

        # NOTE: Knowing the exact student_id makes this query much faster.
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

        return Schedule(
            semester=semester,
            student=student,
            last_modified=last_modified or None,
            version=0,
            semester_version=semester.version,
        )


class WeekNumberConverter:
    regex = r"([1-9]|[1-4][0-9]|5[0-3])"

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
