# This file is part of the plan timetable generator, see LICENSE for details.

from plan.common.models import Course, Exam, Lecture, Semester, Student, Subscription
from plan.common.tests import BaseTestCase


class ManagerTestCase(BaseTestCase):
    fixtures = ["test_data.json", "test_user.json"]

    def test_get_lectures(self):
        # Exclude lectures connected to other courses and excluded from userset
        control = Lecture.objects.exclude(id__in=[6, 7])

        semester = Semester.objects.get(year=2009, type=Semester.SPRING)
        student = Student.objects.get(slug="adamcik")
        lectures = Lecture.objects.get_lectures(semester.id, student.id)

        actual = [l for l in lectures if not l.exclude]
        self.assertEqual(set(actual), set(control))

        # Try showing only lectures in week 1
        actual = [l for l in lectures if 1 in l.week_numbers and not l.exclude]
        self.assertEqual(set(actual), set(control.filter(weeks__number=1)))

        # Try showing lectures in week 2
        actual = [l for l in lectures if 2 in l.week_numbers and not l.exclude]
        self.assertEqual(set(actual), set(control.filter(weeks__number=2)))

        # Try lectures in week 3, ie none
        actual = [l for l in lectures if 3 in l.week_numbers and not l.exclude]
        self.assertEqual(set(actual), set())

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
