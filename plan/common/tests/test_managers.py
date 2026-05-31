# This file is part of the plan timetable generator, see LICENSE for details.

from datetime import time

from plan.common.models import (
    Course,
    Exam,
    Group,
    Lecture,
    Semester,
    Student,
    Subscription,
)
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

    def test_get_lectures_characterization_data_contract(self):
        # This test intentionally characterizes current get_lectures() data
        # semantics (ids/alias/exclude/week_numbers, no duplicates, single-query
        # budget) so we can refactor SQL/ORM shape without changing behavior.
        semester = Semester.objects.get(year=2009, type=Semester.SPRING)
        student = Student.objects.get(slug="adamcik")

        with self.assertNumQueries(1):
            lectures = Lecture.objects.get_lectures(semester.id, student.id)

        self.assertEqual(len(lectures), len({lecture.id for lecture in lectures}))

        expected_ids = set(
            Lecture.objects.filter(course__semester_id=semester.id)
            .exclude(id=6)
            .values_list("id", flat=True)
        )
        self.assertEqual({lecture.id for lecture in lectures}, expected_ids)

        self.assertTrue(all(hasattr(lecture, "alias") for lecture in lectures))
        self.assertTrue(all(hasattr(lecture, "exclude") for lecture in lectures))
        self.assertTrue(all(hasattr(lecture, "week_numbers") for lecture in lectures))
        self.assertTrue(any(lecture.exclude for lecture in lectures))
        self.assertTrue(any(not lecture.exclude for lecture in lectures))
        for lecture in lectures:
            self.assertEqual(
                tuple(sorted(set(lecture.week_numbers))),
                tuple(lecture.week_numbers),
            )

    def test_get_lectures_characterization_avoids_duplicates_for_multiple_groups(self):
        semester = Semester.objects.get(year=2009, type=Semester.SPRING)
        student = Student.objects.get(slug="adamcik")

        subscription = Subscription.objects.filter(
            student=student,
            course__semester=semester,
        ).first()
        self.assertIsNotNone(subscription)

        lecture = Lecture.objects.filter(course=subscription.course).first()
        self.assertIsNotNone(lecture)

        baseline = Lecture.objects.get_lectures(semester.id, student.id)
        baseline_count = sum(1 for item in baseline if item.id == lecture.id)

        extra_group = Group.objects.create(code="CHAR-GROUP", name="Characterization")
        subscription.groups.add(extra_group)
        lecture.groups.add(extra_group)

        updated = Lecture.objects.get_lectures(semester.id, student.id)
        updated_count = sum(1 for item in updated if item.id == lecture.id)

        self.assertEqual(baseline_count, 1)
        self.assertEqual(updated_count, 1)

    def test_get_lectures_returns_empty_week_numbers_without_week_rows(self):
        semester = Semester.objects.get(year=2009, type=Semester.SPRING)
        student = Student.objects.get(slug="adamcik")

        subscription = Subscription.objects.filter(
            student=student,
            course__semester=semester,
        ).first()
        self.assertIsNotNone(subscription)

        group = subscription.groups.first()
        self.assertIsNotNone(group)

        lecture = Lecture.objects.create(
            course=subscription.course,
            title="No weeks lecture",
            summary="",
            stream="",
            day=0,
            start=time(8, 0),
            end=time(9, 0),
            type=None,
        )
        lecture.groups.add(group)

        lectures = Lecture.objects.get_lectures(semester.id, student.id)
        by_id = {item.id: item for item in lectures}
        self.assertIn(lecture.id, by_id)
        self.assertEqual(tuple(by_id[lecture.id].week_numbers), ())

    def test_get_lectures_returns_subscription_alias(self):
        semester = Semester.objects.get(year=2009, type=Semester.SPRING)
        student = Student.objects.get(slug="adamcik")

        subscription = Subscription.objects.filter(
            student=student,
            course__semester=semester,
        ).first()
        self.assertIsNotNone(subscription)

        expected_alias = "Alias Characterization"
        subscription.alias = expected_alias
        subscription.save(update_fields=["alias"])

        lectures = Lecture.objects.get_lectures(semester.id, student.id)
        alias_values = {
            item.alias
            for item in lectures
            if item.course_id == subscription.course_id and hasattr(item, "alias")
        }

        self.assertIn(expected_alias, alias_values)

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
