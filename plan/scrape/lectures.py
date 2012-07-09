# This file is part of the plan timetable generator, see LICENSE for details.

import logging

from django.utils.functional import memoize

from plan.common.models import (Lecture, Lecturer, Room, LectureType,
    Group, Week)

logger = logging.getLogger('plan.scrape.lectures')

def get_or_create_lecture_type(name):
    return LectureType.objects.get_or_create(name=name)[0]

def get_or_create_room(name):
    return Room.objects.get_or_create(name=name)[0]

def get_or_create_lecturer(name):
    return Lecturer.objects.get_or_create(name=name)[0]

def get_or_create_group(name):
    return Group.objects.get_or_create(name=name)[0]

get_or_create_lecture_type= memoize(get_or_create_lecture_type, {}, 1)
get_or_create_room = memoize(get_or_create_room, {}, 1)
get_or_create_lecturer = memoize(get_or_create_lecturer, {}, 1)
get_or_create_group = memoize(get_or_create_group, {}, 1)

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
            lecture_type = get_or_create_lecture_type(row['type'])

        for name in row['rooms']:
            room = get_or_create_room(name)
            rooms.add(room)

        for name in row['lecturers']:
            lecturer = get_or_create_lecturer(name)
            lecturers.add(lecturer)

        for name in row['groups']:
            group = get_or_create_group(name)
            groups.add(group)
        if not groups:
            group = get_or_create_group(Group.DEFAULT)
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
        other_set = set([g.id for g in groups])

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
