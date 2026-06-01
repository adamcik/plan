# This file is part of the plan timetable generator, see LICENSE for details.

from plan.common.models import (
    Course,
    Exam,
    Lecture,
    Semester,
    Student,
    Subscription,
)
from plan.common.tests import BaseTestCase


class ManagerTestCase(BaseTestCase):
    fixtures = ["test_data.json", "test_user.json"]

    def test_get_exams(self):
        exams = Exam.objects.get_exams(2009, Semester.SPRING, "adamcik")
        self.assertEqual(set(exams), set(Exam.objects.exclude(id__in=[3, 4])))

    def test_get_courses(self):
        courses = Course.objects.get_courses(2009, Semester.SPRING, "adamcik")
        self.assertEqual(set(Course.objects.exclude(id__in=[4, 5])), set(courses))

    def test_get_courses_with_exams(self):
        courses = Course.objects.get_courses_with_exams(2009, Semester.SPRING)
        courses = [a[0] for a in courses]

        # Ensure that courses without exams are included and courses with
        # multiple exams on time per exam
        self.assertEqual(courses, [1, 1, 1, 1, 2, 3, 4, 4])

    def test_get_subscriptions(self):
        control = Subscription.objects.filter(id__in=[1, 2, 3])
        subscriptions = Subscription.objects.get_subscriptions(
            2009, Semester.SPRING, "adamcik"
        )
        self.assertEqual(set(control), set(subscriptions))

    def test_search(self):
        control = Course.objects.exclude(id=5).values_list("code", "name")
        courses = Course.objects.search(2009, Semester.SPRING, "COURSE")

        self.assertEqual(set(control), set(courses))

        control = Course.objects.filter(code="COURSE1").values_list("code", "name")
        courses = Course.objects.search(2009, Semester.SPRING, "COURSE1")

        self.assertEqual(set(control), set(courses))
