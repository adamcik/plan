# This file is part of the plan timetable generator, see LICENSE for details.

from plan.common.tests import BaseTestCase
from plan.common.models import Course, Semester


class ModelsTestCase(BaseTestCase):
    fixtures = ["test_data.json", "test_user.json"]

    def test_course_get_stats(self):
        semester = Semester.objects.get(year=2009, type=Semester.SPRING)
        actual = Course.get_stats(semester)

        self.assertEqual(3, actual.pop("slug_count"))
        self.assertEqual(3, actual.pop("course_count"))
        self.assertEqual(6, actual.pop("subscription_count"))

        stats = actual.pop("stats")

        self.assertEqual((3, 2, "COURSE2", "Course 2 full name"), stats[0])
        self.assertEqual((2, 1, "COURSE1", "Course 1 full name"), stats[1])
        self.assertEqual((1, 3, "COURSE3", "Course 3 full name"), stats[2])

    # FIXME test unicode
    # FIXME test course.get_url
    # FIXME test get_stats(int)
    # FIXME test semester.init customisation
