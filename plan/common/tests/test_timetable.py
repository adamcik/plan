# This file is part of the plan timetable generator, see LICENSE for details.

from copy import copy

from plan.common.tests import BaseTestCase
from plan.common.models import Lecture, Semester
from plan.common.timetable import Timetable

class TimetableTestCase(BaseTestCase):
    maxDiff = None
    fixtures = ['test_data.json', 'test_user.json']

    def test_timetable(self):
        # FIXME test expansion
        # FIXME test instert times
        # FIXME test map_to_slot

        lectures = Lecture.objects.get_lectures(2009, Semester.SPRING, 'adamcik')

        timetable = Timetable(lectures)
        timetable.place_lectures()
        timetable.add_markers()

        rows = []
        bottom = {'bottom': True}
        last = {'last': True}
        bottomlast = {'bottom': True, 'last': True}

        lectures  = dict((l.id, l) for l in lectures)
        lecture2  = {'lecture': lectures[2],  'rowspan': 2,  'remove': False, 'bottom': False}
        lecture3  = {'lecture': lectures[3],  'rowspan': 2,  'remove': False, 'bottom': False}
        lecture4  = {'lecture': lectures[4],  'rowspan': 6,  'remove': False, 'bottom': False}
        lecture5  = {'lecture': lectures[5],  'rowspan': 2,  'remove': False, 'bottom': False, 'last': True}
        lecture8  = {'lecture': lectures[8],  'rowspan': 1,  'remove': False, 'bottom': False}
        lecture9  = {'lecture': lectures[9],  'rowspan': 12, 'remove': False, 'bottom': True,  'last': True}
        lecture10 = {'lecture': lectures[10], 'rowspan': 1,  'remove': False, 'bottom': False, 'last': True}
        lecture11 = {'lecture': lectures[11], 'rowspan': 1,  'remove': False, 'bottom': True,  'last': True}

        rows.append([[lecture2, lecture4, last], [lecture9], [lecture10], [last], [last]])

        lecture2 = copy(lecture2)
        lecture2['remove'] = True
        lecture9 = copy(lecture9)
        lecture9['remove'] = True
        lecture9['bottom'] = False

        lecture4 = copy(lecture4)
        lecture4['remove'] = True

        rows.append([[lecture2, lecture4, lecture5], [lecture9], [last], [last], [last]])

        lecture5 = copy(lecture5)
        lecture5['remove'] = True

        rows.append([[lecture3, lecture4, lecture5], [lecture9], [last], [last], [last]])

        lecture3 = copy(lecture3)
        lecture3['remove'] = True

        rows.append([[lecture3, lecture4, last],       [lecture9], [last],      [last],       [last]])
        rows.append([[{},       lecture4, last],       [lecture9], [last],      [last],       [last]])
        rows.append([[{},       lecture4, last],       [lecture9], [last],      [last],       [last]])
        rows.append([[{},       {},       last],       [lecture9], [last],      [last],       [last]])
        rows.append([[lecture8, {},       last],       [lecture9], [last],      [last],       [last]])
        rows.append([[{},       {},       last],       [lecture9], [last],      [last],       [last]])
        rows.append([[{},       {},       last],       [lecture9], [last],      [last],       [last]])
        rows.append([[{},       {},       last],       [lecture9], [last],      [last],       [last]])
        rows.append([[bottom,   bottom,   bottomlast], [lecture9], [lecture11], [bottomlast], [bottomlast]])

        for i, (t, r) in enumerate(zip(timetable.table, rows)):
            self.assertEquals(t, r)
