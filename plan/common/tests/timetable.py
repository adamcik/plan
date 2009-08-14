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

from copy import copy

from plan.common.tests.base import BaseTestCase
from plan.common.models import Lecture, Semester
from plan.common.timetable import Timetable

class TimetableTestCase(BaseTestCase):
    fixtures = ['test_data.json', 'test_user.json']

    def test_timetable(self):
        # FIXME test expansion
        # FIXME test instert times
        # FIXME test map_to_slot

        lectures = Lecture.objects.get_lectures(2009, Semester.SPRING, 'adamcik')

        timetable = Timetable(lectures)
        timetable.place_lectures()

        rows = []

        lectures  = dict([(l.id, l) for l in lectures])
        lecture2  = {'lecture': lectures[2],  'rowspan': 2,  'remove': False}
        lecture3  = {'lecture': lectures[3],  'rowspan': 2,  'remove': False}
        lecture4  = {'lecture': lectures[4],  'rowspan': 6,  'remove': False}
        lecture5  = {'lecture': lectures[5],  'rowspan': 2,  'remove': False}
        lecture8  = {'lecture': lectures[8],  'rowspan': 1,  'remove': False}
        lecture9  = {'lecture': lectures[9],  'rowspan': 12, 'remove': False}
        lecture10 = {'lecture': lectures[10], 'rowspan': 1,  'remove': False}
        lecture11 = {'lecture': lectures[11], 'rowspan': 1,  'remove': False}

        rows.append([[lecture2, lecture4, {}],       [lecture9], [lecture10], [{}], [{}]])

        lecture2 = copy(lecture2)
        lecture2['remove'] = True
        lecture9 = copy(lecture9)
        lecture9['remove'] = True

        lecture4 = copy(lecture4)
        lecture4['remove'] = True

        rows.append([[lecture2, lecture4, lecture5], [lecture9], [{}], [{}], [{}]])

        lecture5 = copy(lecture5)
        lecture5['remove'] = True

        rows.append([[lecture3, lecture4, lecture5], [lecture9], [{}], [{}], [{}]])

        lecture3 = copy(lecture3)
        lecture3['remove'] = True

        rows.append([[lecture3, lecture4, {}],       [lecture9], [{}], [{}], [{}]])
        rows.append([[{},       lecture4, {}],       [lecture9], [{}], [{}], [{}]])
        rows.append([[{},       lecture4, {}],       [lecture9], [{}], [{}], [{}]])
        rows.append([[{},       {},       {}],       [lecture9], [{}], [{}], [{}]])
        rows.append([[lecture8, {},       {}],       [lecture9], [{}], [{}], [{}]])
        rows.append([[{},       {},       {}],       [lecture9], [{}], [{}], [{}]])
        rows.append([[{},       {},       {}],       [lecture9], [{}], [{}], [{}]])
        rows.append([[{},       {},       {}],       [lecture9], [{}], [{}], [{}]])
        rows.append([[{},       {},       {}],       [lecture9], [lecture11], [{}], [{}]])

        for t,r in zip(timetable.table, rows):
            self.assertEquals(t,r)
