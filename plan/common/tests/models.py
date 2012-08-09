# This file is part of the plan timetable generator, see LICENSE for details.

from plan.common.tests.base import BaseTestCase
from plan.common.models import Course, Semester

class ModelsTestCase(BaseTestCase):
    fixtures = ['test_data.json', 'test_user.json']

    def test_course_get_stats(self):
        semester = Semester.objects.get(year=2009, type=Semester.SPRING)
        actual = Course.get_stats(semester)

        self.assertEquals(3, actual.pop('slug_count'))
        self.assertEquals(3, actual.pop('course_count'))
        self.assertEquals(6, actual.pop('subscription_count'))

        stats = actual.pop('stats')

        self.assertEquals((3, 2, u'COURSE2', u'Course 2 full name'), stats[0])
        self.assertEquals((2, 1, u'COURSE1', u'Course 1 full name'), stats[1])
        self.assertEquals((1, 3, u'COURSE3', u'Course 3 full name'), stats[2])

        self.assertEquals(15, actual.pop('limit'))

        self.assertEquals({}, actual)

    # FIXME test unicode
    # FIXME test course.get_url
    # FIXME test get_stats(int)
    # FIXME test semester.init customisation
    # FIXME test get_first and last day
    # FIXME test semester.next
    # FIXME test semester.current
