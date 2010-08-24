# Copyright 2010 Thomas Kongevold Adamcik

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

import logging
from dateutil.parser import parse

from plan.common.models import (Lecture, Lecturer, Room, LectureType,
    Group, Week)

logger = logging.getLogger('plan.scrape.lectures')
days_of_week_no = ['mandag', 'tirsdag', 'onsdag', 'torsdag', 'fredag']
days_of_week_en = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']

def get_day_of_week(value):
    value = value.lower().strip()

    if value in days_of_week_no:
        return days_of_week_no.index(value)
    elif value in days_of_week_en:
        return days_of_week_en.index(value)
    else:
        return None

def get_time(value):
    if not value.strip():
        return None
    return parse(value.strip()).time()

def get_weeks(values):
    weeks = []
    for week in values:
        if '-' in week:
            x, y = week.split('-')
            weeks.extend(range(int(x), int(y)+1))
        else:
            weeks.append(int(week.replace(',', '')))
    return weeks

def process_lectures(data):
    added_lectures = []

    for row in data:
        added = False
        lecture_type = None
        weeks = row['weeks']
        rooms = set()
        lecturers = set()
        groups = set()

        if row['type']:
            lecture_type, created = LectureType.objects.get_or_create(name=row['type'])

        for room in row['rooms']:
            room, created = Room.objects.get_or_create(name=room)
            rooms.add(room)

        for lecturer in row['lecturers']:
            lecturer, created = Lecturer.objects.get_or_create(name=lecturer)
            lecturers.add(lecturer)

        for group in row['groups']:
            group, created = Group.objects.get_or_create(name=group)
            groups.add(group)
        if not groups:
            group, created = Group.objects.get_or_create(name=Group.DEFAULT)
            groups = [group]

        lecture_kwargs = {
            'course': row['course'],
            'day': row['day'],
            'start': row['start'],
            'end': row['end'],
            'type': lecture_type,
        }

        if not lecture_type:
            del lecture_kwargs['type']

        lectures = Lecture.objects.filter(**lecture_kwargs).order_by('id')
        lectures = list(lectures.exclude(id__in=added_lectures))
        other_set = set(map(lambda g: g.id, groups))

        for lecture in lectures:
            # FIXME this handling does strictly speaking work, but it is not
            # stable. ie. which dupe ends up with which room/lecturer/week is
            # somewhat random
            psql_set = set(lecture.groups.values_list('id', flat=True))

            if psql_set == other_set:
                # FIXME need extra check against weeks and rooms
                added = True
                break

        if not added:
            lecture = Lecture(**lecture_kwargs)
            lecture.save()

        added_lectures.append(lecture.id)

        lecture.rooms = list(rooms)
        lecture.lecturers = list(lecturers)
        lecture.groups = list(groups)
        lecture.save()

        Week.objects.filter(lecture=lecture).delete()
        for week in weeks:
            Week.objects.create(lecture=lecture, number=week)

        logger.info(u'Saved %s' % lecture)

    return added_lectures
