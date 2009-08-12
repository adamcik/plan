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

from datetime import date
from dateutil.rrule import rrule, MO, TU, WE, TH, FR, DAILY

from plan.common.models import Lecture

class Timetable:
    slots = 12

    def __init__(self, lectures, rooms={}):
        self.lecture_queryset = lectures
        self.lectures = []
        self.table = [[[{}] for a in Lecture.DAYS] for b in range(self.slots)]
        self.span = [1] * 5
        self.date = [] * 5

        self.rooms = rooms

    def set_week(self, year, week):
        self.date = map(lambda d: d.date(), rrule(DAILY, count=5,
                byweekday=(MO,TU,WE,TH,FR), byweekno=week, dtstart=date(year, 1, 1)))

    def place_lectures(self):
        '''Add basics to datastructure'''

        for i, lecture in enumerate(self.lecture_queryset):
            if lecture.exclude or not lecture.show_week:
                continue

            start, end = self.map_to_slot(lecture)
            rowspan = end - start + 1

            first = start

            # Try to find leftmost row that can fit our lecture, if we run out of
            # rows to test, ie IndexError, we append a fresh one to work with
            try:
                row = 0
                while start <= end:
                    if self.table[start][lecture.day][row]:
                        # One of our time slots is taken, bump the row number and
                        # restart our search
                        row += 1
                        start = first
                    else:
                        start += 1

            except IndexError:
                # We ran out of rows to check, simply append a new row
                for j in range(self.slots):
                    self.table[j][lecture.day].append({})

                # Update the header colspan
                self.span[lecture.day] += 1

            start = first
            remove = False

            while start <= end:
                # Replace the cell we found with a base containing info about our
                # lecture
                self.table[start][lecture.day][row] = {
                    'lecture': lecture,
                    'rowspan': rowspan,
                    'remove': remove,
                }

                # Add lecture to our supplementary data structure and set the
                # remove flag.
                if not remove:
                    remove = True
                    self.lectures.append({
                        'height': rowspan,
                        'i': start,
                        'j': lecture.day,
                        'k': row,
                        'l': lecture,
                    })

                start += 1

    def do_expansion(self):
        for lecture in self.lectures:
            # Loop over supplementary data structure using this to figure out which
            # colspan expansions are safe
            i = lecture['i']
            j = lecture['j']
            k = lecture['k']

            height = lecture['height']

            expand_by = 1

            # Add rooms
            r = self.rooms.get(self.table[i][j][k]['lecture'].id, [])

            self.table[i][j][k]['lecture'].sql_rooms = r

            # Find safe expansion of colspan
            safe = True
            for l in xrange(k+1, len(self.table[i][j])):
                for m in xrange(i, i+height):
                    if self.table[m][j][l]:
                        safe = False
                        break
                if safe:
                    expand_by += 1
                else:
                    break

            self.table[i][j][k]['colspan'] = expand_by
            lecture['width'] = expand_by

            if k+expand_by == len(self.table[i][j]):
                self.table[i][j][k]['last'] = True

            # Remove cells that will get replaced by colspan
            for l in xrange(k+1, k+expand_by):
                for m in xrange(i, i+height):
                    self.table[m][j][l]['remove'] = True


    def add_last_marker(self):
        # Add last marker
        for day in self.table:
            for slot in day:
                slot[-1]['last'] = True

    # FIXME add an insert_days method

    def insert_times(self):

        for i in range(8, 20):
            self.table[i-8].insert(0, [{'time': '%02d:15 - %02d:00' % (i, i+1), 'last': True }])

    def map_to_slot(self, lecture):
        '''Maps a given lecture to zero-indexed start and stop slots
           ensuring that start < end'''

        start = lecture.start.hour
        end = lecture.end.hour

        if start >= 0 and start < 4:
            start += 24

        if end >= 0 and end < 4:
            end += 24

        if start == end:
            end += 1

        if start < 8:
            start = 8

        if end < 9:
            end = 9

        if start > 19:
            start = 19

        if end > 20:
            end = 20

        return (start-8, end-9)
