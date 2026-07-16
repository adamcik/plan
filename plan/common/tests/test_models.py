# This file is part of the plan timetable generator, see LICENSE for details.

import datetime
import re

import pytest
from plan.common.models import Course, Exam, Lecture, LectureType, Semester
from plan.materialized.models import SemesterAnalytics, TopCourses


pytestmark = pytest.mark.django_db


def test_course_get_stats(serialized_schedule_data, cache_isolation, frozen_time):
    SemesterAnalytics.refresh_view()
    TopCourses.refresh_view()

    semester = Semester.objects.get(year=2009, type=Semester.SPRING)

    actual = Course.get_stats(semester, bypass_cache=True)

    assert actual.pop("slug_count") == 3
    assert actual.pop("course_count") == 3
    assert actual.pop("subscription_count") == 6

    stats = actual.pop("stats")

    assert stats[0] == (3, 2, "COURSE2", "Course 2 full name")
    assert stats[1] == (2, 1, "COURSE1", "Course 1 full name")
    assert stats[2] == (1, 3, "COURSE3", "Course 3 full name")


def test_lecture_str_uses_24h_time(
    serialized_schedule_data, cache_isolation, frozen_time
):
    course = Course.objects.order_by("id").first()
    lecture_type = LectureType.objects.get_or_create(name="Lecture", code="LEC")[0]
    lecture = Lecture.objects.create(
        course=course,
        type=lecture_type,
        day=0,
        start=datetime.time(9, 15),
        end=datetime.time(10, 0),
    )

    value = str(lecture)

    assert re.search(r"\b\d{2}:\d{2}-\d{2}:\d{2}\b", value)
    assert not re.search(r"\b(AM|PM|a\.m\.|p\.m\.)\b", value)


def test_lecture_short_name_uses_24h_time(
    serialized_schedule_data, cache_isolation, frozen_time
):
    course = Course.objects.order_by("id").first()
    lecture_type = LectureType.objects.get_or_create(name="Seminar", code="SEM")[0]
    lecture = Lecture.objects.create(
        course=course,
        type=lecture_type,
        day=1,
        start=datetime.time(14, 5),
        end=datetime.time(16, 45),
    )

    value = lecture.short_name

    assert re.search(r"\b\d{2}:\d{2}-\d{2}:\d{2}\b", value)
    assert not re.search(r"\b(AM|PM|a\.m\.|p\.m\.)\b", value)


def test_exam_str_uses_iso_date(serialized_schedule_data, cache_isolation, frozen_time):
    exam = Exam.objects.exclude(exam_date=None).get(pk=1)

    assert re.search(r"\b\d{4}-\d{2}-\d{2}\b", str(exam))


def test_course_str_uses_semester_id_without_fk_query(
    serialized_schedule_data, cache_isolation, frozen_time, django_assert_num_queries
):
    course = Course.objects.get(pk=1)

    with django_assert_num_queries(0):
        value = str(course)

    assert "semester_id=1" in value
    assert "(spring" not in value.lower()


def test_course_str_includes_semester_details_when_loaded(
    serialized_schedule_data, cache_isolation, frozen_time, django_assert_num_queries
):
    course = Course.objects.select_related("semester").get(pk=1)

    with django_assert_num_queries(0):
        value = str(course)

    assert "semester_id=1" in value
    assert "(" in value


# FIXME test unicode
# FIXME test course.get_url
# FIXME test get_stats(int)
# FIXME test semester.init customisation
