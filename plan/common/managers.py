# This file is part of the plan timetable generator, see LICENSE for details.

import datetime

from django.db import connection, models


def today():
    return datetime.date.today()


class LectureManager(models.Manager):
    def get_lectures(self, semester_id, student_id):
        """
        Get all lectures for subscription during given period.

        To do this we need to pull in a bunch of extra tables and manually join them
        in the where clause. The first element in the custom where is the important
        one that limits our results, the rest are simply meant for joining.
        """

        where = [
            "common_subscription_groups.group_id = common_group.id",
            "common_subscription_groups.subscription_id = common_subscription.id",
            "common_group.id = common_lecture_groups.group_id",
            "common_lecture_groups.lecture_id = common_lecture.id",
        ]
        tables = ["common_subscription_groups", "common_group", "common_lecture_groups"]

        select = {
            "alias": "common_subscription.alias",
            "exclude": """
                EXISTS (SELECT 1
                 FROM common_subscription_exclude WHERE
                 common_subscription_exclude.subscription_id = common_subscription.id AND
                 common_subscription_exclude.lecture_id = common_lecture.id)""",
            "week_numbers": """
                COALESCE((
                    SELECT ARRAY_AGG(DISTINCT w.number ORDER BY w.number)
                    FROM common_week w
                    WHERE w.lecture_id = common_lecture.id
                ), '{}'::integer[])""",
        }

        filter_kwargs = {
            "course__subscription__student_id": student_id,
            "course__semester_id": semester_id,
        }

        related = [
            "type",
            "course",
        ]

        fields = [
            "id",
            "course_id",
            "title",
            "summary",
            "stream",
            "day",
            "start",
            "end",
            "course__code",
            "course__name",
            "type_id",
            "type__code",
            "type__name",
            "type__optional",
        ]

        order = [
            "course__code",
            "day",
            "start",
            "type__name",
            "type__code",
            "type__optional",
            "course_id",
            "type_id",
            "id",
        ]

        return list(
            self.get_queryset()
            .filter(**filter_kwargs)
            .distinct()
            .select_related(*related)
            .extra(where=where, tables=tables, select=select)
            .only(*fields)
            .order_by(*order)
        )


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

        return [row for (code, row) in sorted(result.items(), key=priority)]


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
