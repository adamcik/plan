# Copyright 2008, 2009 Thomas Kongevold Adamcik
# 2009 IME Faculty Norwegian University of Science and Technology

# This file is part of Plan.
#
# Plan is free software: you can redistribute it and/or modify
# it under the terms of the Affero GNU General Public License as 
# published by the Free Software Foundation, either version 3 of
# the License, or (at your option) any later version.
#
# Plan is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# Affero GNU General Public License for more details.
#
# You should have received a copy of the Affero GNU General Public
# License along with Plan.  If not, see <http://www.gnu.org/licenses/>.

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
        self.assertEquals(3, actual.pop('deadline_count'))

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
    # FIXME test deadline.get_datetime
    # FIXME test deadline.get_slug
    # FIXME test deadline.get_course
