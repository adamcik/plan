# This file is part of the plan timetable generator, see LICENSE for details.

import datetime

from django.db import connection
from django.db import models

from plan.common.utils import build_search


class LectureManager(models.Manager):
    def get_lectures(self, year, semester_type, slug=None, week=None, course=None):
        """
        Get all lectures for subscription during given period.

        To do this we need to pull in a bunch of extra tables and manualy join them
        in the where cluase. The first element in the custom where is the important
        one that limits our results, the rest are simply meant for joining.
        """

        if not slug and not course:
            raise Exception("Invalid invocation of get_lectures")
        elif slug and course:
            raise Exception("Invalid invocation of get_lectures")

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
            "show_week": "%s",
        }

        if week:
            select[
                "show_week"
            ] = """
                EXISTS (SELECT 1 FROM common_week w WHERE
                    w.lecture_id = common_lecture.id AND w.number = %s)"""

        if slug:
            filter_kwargs = {
                "course__subscription__student__slug": slug,
                "course__semester__year__exact": year,
                "course__semester__type__exact": semester_type,
            }
        else:
            filter_kwargs = {
                "course__name": course,
                "course__semester__year__exact": year,
                "course__semester__type__exact": semester_type,
            }
            where = []
            tables = []
            select["alias"] = "NULL"
            select["exclude"] = "False"

        related = [
            "type",
            "course",
        ]

        order = [
            "course__code",
            "day",
            "start",
            "type__name",
        ]

        params = [week or True]

        return list(
            self.get_queryset()
            .filter(**filter_kwargs)
            .distinct()
            .select_related(*related)
            .extra(where=where, tables=tables, select=select, select_params=params)
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

    def search(self, year, semester_type, query, limit=10, location=None):
        search_filter = build_search(
            query, ["code__icontains", "name__icontains", "subscription__alias__exact"]
        )

        qs = self.get_queryset()
        qs = qs.filter(search_filter)
        qs = qs.filter(semester__year__exact=year, semester__type__exact=semester_type)
        if location:
            qs = qs.filter(locations__id=location)

        qs = qs.distinct()
        qs = qs.order_by("code")

        return qs[:limit]


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
        qs = qs.filter(active__lt=datetime.date.today())
        try:
            return qs.order_by("-active")[0]
        except IndexError:
            raise self.model.DoesNotExist

    def __next__(self):
        return self.next()

    def next(self):
        qs = self.get_queryset()
        qs = qs.filter(active__gte=datetime.date.today())
        try:
            return qs.order_by("active")[0]
        except IndexError:
            raise self.model.DoesNotExist
