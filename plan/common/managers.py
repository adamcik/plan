# This file is part of the plan timetable generator, see LICENSE for details.

import datetime
from collections.abc import Iterator
from collections.abc import Mapping
from typing import Any

from django.db import connection, models

from plan.common.lecture_data import LectureData, Weekday


def today():
    return datetime.date.today()


def _iter_cursor_dicts(cursor) -> Iterator[Mapping[str, Any]]:
    column_index = {column[0]: index for index, column in enumerate(cursor.description)}
    for row in cursor:
        yield {name: row[index] for name, index in column_index.items()}


class LectureManager(models.Manager):
    def get_lectures_data(self, semester_id, student_id):
        cursor = connection.cursor()
        cursor.execute(
            """
            WITH student_subs AS (
                SELECT s.id, s.course_id, s.alias
                FROM common_subscription s
                JOIN common_course c ON c.id = s.course_id
                WHERE s.student_id = %(student_id)s
                  AND c.semester_id = %(semester_id)s
            )
            SELECT
                l.id AS lecture_id,
                l.title,
                l.summary,
                l.stream,
                l.day,
                l.start,
                l."end",
                COALESCE(w.week_numbers, '{}'::integer[]) AS week_numbers,
                ss.alias,
                EXISTS (
                    SELECT 1
                    FROM common_subscription_exclude se
                    WHERE se.subscription_id = ss.id
                      AND se.lecture_id = l.id
                ) AS exclude,
                c.id AS course_id,
                c.code AS course_code,
                c.name AS course_name,
                lt.id AS type_id,
                lt.code AS type_code,
                lt.name AS type_name,
                COALESCE(lt.optional, FALSE) AS type_optional
            FROM student_subs ss
            JOIN common_course c ON c.id = ss.course_id
            JOIN common_lecture l ON l.course_id = c.id
            LEFT JOIN common_lecturetype lt ON lt.id = l.type_id
            LEFT JOIN LATERAL (
                SELECT ARRAY_AGG(DISTINCT w.number ORDER BY w.number) AS week_numbers
                FROM common_week w
                WHERE w.lecture_id = l.id
            ) w ON TRUE
            WHERE EXISTS (
                SELECT 1
                FROM common_subscription_groups sg
                JOIN common_lecture_groups lg ON lg.group_id = sg.group_id
                WHERE sg.subscription_id = ss.id
                  AND lg.lecture_id = l.id
            )
            ORDER BY
                c.code ASC,
                l.day ASC,
                l.start ASC,
                lt.name ASC,
                lt.code ASC,
                lt.optional ASC,
                l.course_id ASC,
                l.type_id ASC,
                l.id ASC
            """,
            {
                "student_id": student_id,
                "semester_id": semester_id,
            },
        )

        return [
            LectureData(
                lecture_id=row["lecture_id"],
                title=row["title"],
                summary=row["summary"],
                stream=row["stream"],
                day=Weekday(row["day"]),
                start=row["start"],
                end=row["end"],
                week_numbers=tuple(sorted(set(row["week_numbers"] or ()))),
                alias=row["alias"] or None,
                exclude=row["exclude"],
                course_id=row["course_id"],
                course_code=row["course_code"],
                course_name=row["course_name"],
                type_id=row["type_id"],
                type_code=row["type_code"],
                type_name=row["type_name"],
                type_optional=row["type_optional"],
            )
            for row in _iter_cursor_dicts(cursor)
        ]


class ExamManager(models.Manager):
    def get_exams(self, year, semester_type, slug=None, course=None):
        if not slug and not course:
            raise Exception("Invalid invocation of get_exams")
        elif slug and course:
            raise Exception("Invalid invocation of get_exams")

        if slug:
            exam_filter = {
                "course__subscription__student__slug": slug,
                "course__semester__year__exact": year,
                "course__semester__type__exact": semester_type,
            }
            select = {"alias": "common_subscription.alias"}
        else:
            exam_filter = {
                "course__name": course,
                "course__semester__year__exact": year,
                "course__semester__type__exact": semester_type,
            }
            select = {}

        return (
            self.get_queryset()
            .filter(**exam_filter)
            .select_related(
                "course",
                "type",
            )
            .extra(select=select)
            .order_by("handout_date", "handout_time", "exam_date", "exam_time")
        )


class CourseManager(models.Manager):
    def get_courses(self, year, semester_type, slug):
        course_filter = {
            "subscription__student__slug": slug,
            "subscription__course__semester__year__exact": year,
            "subscription__course__semester__type__exact": semester_type,
        }
        return (
            self.get_queryset()
            .filter(**course_filter)
            .extra(select={"alias": "common_subscription.alias"})
            .distinct()
            .order_by("code")
        )

    def get_courses_with_exams(self, year, semester_type):
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT c.id as id, c.code, c.name, c.points,
                   e.exam_date, e.exam_time, et.code, et.name,
                   e.handout_date, e.handout_time
            FROM common_course c
            JOIN common_semester s ON
                (c.semester_id = s.id)
            LEFT OUTER JOIN common_exam e ON
                (e.course_id = c.id)
            LEFT OUTER JOIN common_examtype et ON
                (e.type_id = et.id)
            WHERE s.year = %s AND s.type = %s
            ORDER BY c.code, e.exam_date, e.exam_time, et.code;
        """,
            [year, semester_type],
        )

        return cursor.fetchall()

    def search(self, year, semester_type, query, limit=100, location=None):
        from plan.common.models import Semester
        from plan.common.utils import build_search, parse_query

        try:
            semester = Semester.objects.get(year=year, type=semester_type)
        except Semester.DoesNotExist:
            return []

        terms = parse_query(query.upper())
        search_filter = build_search(terms, ["code__icontains", "name__icontains"])
        alias_filter = build_search(terms, ["subscription__alias__iexact"])

        qs = self.get_queryset().filter(semester=semester)
        if location:
            qs = qs.filter(locations__id=location)

        # TODO: Consider adding location to output, this would require doing lookup
        # starting from location instead of course objects to be efficient.
        qs = qs.values_list("code", "name")

        result = {}
        for code, name in qs.filter(search_filter):
            result[code.upper()] = (code, name)
        for code, name in qs.filter(alias_filter):
            result[code.upper()] = (code, name)

        def priority(pair):
            return (0 if any(pair[0].startswith(p) for p in terms) else 1, pair[0])

        rows = [row for (code, row) in sorted(result.items(), key=priority)]
        return rows[: max(0, limit)]


class SubscriptionManager(models.Manager):
    def get_subscriptions(self, year, semester_type, slug):
        return (
            self.get_queryset()
            .filter(
                student__slug=slug,
                course__semester__year__exact=year,
                course__semester__type__exact=semester_type,
            )
            .select_related(
                "course",
            )
            .order_by("student__slug", "course__code")
        )


class SemesterManager(models.Manager):
    def active(self):
        qs = self.get_queryset()
        qs = qs.filter(active__lt=today())
        try:
            return qs.order_by("-active")[0]
        except IndexError:
            raise self.model.DoesNotExist

    def __next__(self):
        return self.next()

    def next(self):
        qs = self.get_queryset()
        qs = qs.filter(active__gte=today())
        try:
            return qs.order_by("active")[0]
        except IndexError:
            raise self.model.DoesNotExist
