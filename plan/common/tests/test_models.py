# This file is part of the plan timetable generator, see LICENSE for details.

import datetime

from plan.common.models import Course, Exam, Lecture, LectureType, Semester
from plan.common.tests import BaseTestCase
from plan.materialized.models import SemesterAnalytics, TopCourses


class ModelsTestCase(BaseTestCase):
    fixtures = ["test_data.json", "test_user.json"]

    def test_course_get_stats(self):
        SemesterAnalytics.refresh_view()
        TopCourses.refresh_view()

        semester = Semester.objects.get(year=2009, type=Semester.SPRING)

        actual = Course.get_stats(semester, bypass_cache=True)

        self.assertEqual(3, actual.pop("slug_count"))
        self.assertEqual(3, actual.pop("course_count"))
        self.assertEqual(6, actual.pop("subscription_count"))

        stats = actual.pop("stats")

        self.assertEqual((3, 2, "COURSE2", "Course 2 full name"), stats[0])
        self.assertEqual((2, 1, "COURSE1", "Course 1 full name"), stats[1])
        self.assertEqual((1, 3, "COURSE3", "Course 3 full name"), stats[2])

    def test_lecture_str_uses_24h_time(self):
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

        self.assertRegex(value, r"\b\d{2}:\d{2}-\d{2}:\d{2}\b")
        self.assertNotRegex(value, r"\b(AM|PM|a\.m\.|p\.m\.)\b")

    def test_lecture_short_name_uses_24h_time(self):
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

        self.assertRegex(value, r"\b\d{2}:\d{2}-\d{2}:\d{2}\b")
        self.assertNotRegex(value, r"\b(AM|PM|a\.m\.|p\.m\.)\b")

    def test_exam_str_uses_iso_date(self):
        exam = Exam.objects.exclude(exam_date=None).get(pk=1)

        value = str(exam)

        self.assertRegex(value, r"\b\d{4}-\d{2}-\d{2}\b")

    def test_course_str_uses_semester_id_without_fk_query(self):
        course = Course.objects.get(pk=1)

        with self.assertNumQueries(0):
            value = str(course)

        self.assertIn("semester_id=1", value)
        self.assertNotIn("(spring", value.lower())

    def test_course_str_includes_semester_details_when_loaded(self):
        course = Course.objects.select_related("semester").get(pk=1)

        with self.assertNumQueries(0):
            value = str(course)

        self.assertIn("semester_id=1", value)
        self.assertIn("(", value)

    # FIXME test unicode
    # FIXME test course.get_url
    # FIXME test get_stats(int)
    # FIXME test semester.init customisation
