"""Domain records constructed offline, never another capture format.

A decoder turns opaque source results into SemesterRecords. Its course roster
scopes lecture and examination identities before database rows exist. Validation
establishes those relationships before the importer may open a transaction.
"""

import datetime
from typing import Annotated, Self

import pydantic

from plan.scrape.snapshot import Semester

_NonBlank = Annotated[str, pydantic.StringConstraints(pattern=r"\S")]


class _Model(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(strict=True, extra="forbid")


class CourseIdentity(_Model):
    code: _NonBlank
    version: _NonBlank | None


class CourseRecord(CourseIdentity):
    """Roster metadata; syllabus None is unobserved, while an empty URL is absence."""

    name: _NonBlank
    url: str
    locations: list[_NonBlank]
    syllabus: str | None = None

    @pydantic.field_validator("locations")
    @classmethod
    def _validate_locations(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("duplicate locations")

        return values


class LectureRecord(_Model):
    """A recurring weekly slot, grouping source activities across multiple weeks."""

    course: CourseIdentity
    type: _NonBlank
    day: Annotated[int, pydantic.Field(ge=0, le=6)]
    start: datetime.time
    end: datetime.time
    weeks: Annotated[
        list[Annotated[int, pydantic.Field(ge=1, le=53)]], pydantic.Field(min_length=1)
    ]
    rooms: list[tuple[str, str, str]]
    groups: list[_NonBlank]
    lecturers: list[_NonBlank]
    title: str | None
    summary: str | None
    stream: str | None

    @pydantic.field_validator("groups", "lecturers")
    @classmethod
    def _validate_members(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("duplicate lecture members")

        return values

    @pydantic.model_validator(mode="after")
    def _validate_interval(self) -> Self:
        if self.day > 4:
            raise ValueError("weekend lectures are not supported by Plan")

        if (
            self.start.tzinfo is not None
            or self.end.tzinfo is not None
            or self.end <= self.start
        ):
            raise ValueError("invalid lecture interval")

        return self


class ExaminationRecord(_Model):
    course: CourseIdentity
    date: datetime.date


class SemesterRecords(_Model):
    """Authoritative domain observations for one semester, ready for reconciliation."""

    semester: Semester
    courses: list[CourseRecord]
    lectures: list[LectureRecord]
    examinations: list[ExaminationRecord]

    @pydantic.model_validator(mode="after")
    def _validate_semester(self) -> Self:
        if not self.courses:
            raise ValueError("cannot import an empty complete course inventory")

        identities = {(course.code, course.version) for course in self.courses}
        if len(identities) != len(self.courses):
            raise ValueError("duplicate course identity")

        for name in ("lectures", "examinations"):
            seen = set()
            for record in getattr(self, name):
                if (record.course.code, record.course.version) not in identities:
                    raise ValueError(f"unknown {name} course reference")

                key = record.model_dump_json()
                if key in seen:
                    raise ValueError(f"duplicate {name} record")

                seen.add(key)

        for exam in self.examinations:
            if exam.date.year != self.semester.year or (exam.date.month <= 6) != (
                self.semester.type == "spring"
            ):
                raise ValueError("examination is outside the snapshot semester")

        return self
