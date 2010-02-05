# encoding: utf-8

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

import logging
import re
from decimal import Decimal
from dateutil.parser import parse

from django.db import transaction
from django.conf import settings

from plan.common.models import Course, Lecture, Lecturer, Semester, Group, \
        LectureType, Week, Room

logger = logging.getLogger('scrape.db')

def _connection():
    import MySQLdb

    mysql_setings = {
        'db': settings.MYSQL_NAME,
        'host': settings.MYSQL_HOST,
        'user': settings.MYSQL_USER,
        'passwd': settings.MYSQL_PASSWORD,
        'use_unicode': True,
    }

    return MySQLdb.connect(**mysql_setings)

def update_lectures(year, semester_type, prefix=None, matches=None):
    '''Retrive all lectures for a given course'''

    semester, created = Semester.objects.get_or_create(year=year, type=semester_type)

    prefix = prefix or semester.prefix

    logger.debug('Using prefix: %s', prefix)

    db = _connection()
    c = db.cursor()

    query = """
            SELECT emnekode,typenavn,dag,start,slutt,uke,romnavn,larer,studentset
            FROM %s_timeplan WHERE emnekode NOT LIKE '#%%'
        """ % prefix

    if matches:
        logger.info('Limiting to %s*', matches)

        query  = query.replace('%', '%%')
        query += ' AND emnekode LIKE %s'
        query += ' ORDER BY emnekode, dag, start, slutt, uke, romnavn'
        c.execute(query, (matches + '%',))
    else:
        query += ' ORDER BY emnekode, dag, start, slutt, uke, romnavn'
        c.execute(query)

    added_lectures = []
    mysql_lecture_count = 0
    skipped = 0

    lectures = Lecture.objects.filter(course__semester=semester)

    if matches:
        lectures = lectures.filter(course__code__startswith=matches)

    for l in lectures:
        l.rooms.clear()
        l.lecturers.clear()
        Week.objects.filter(lecture=l).delete()

    for row in c.fetchall():
        code, course_type, day, start, end, week, room, lecturer, studentset = row
        if not code.strip():
            continue

        mysql_lecture_count += 1
        skipped += 1

        # Remove -1 etc. from course code
        code = '-'.join(code.split('-')[:-1]).upper()

        if not re.match(settings.TIMETABLE_VALID_COURSE_NAMES, code):
            logging.info('Skipped %s', code)
            continue

        # Get and or update course
        course, created = Course.objects.get_or_create(code=code, semester=semester)

        # Load or create type:
        if course_type:
            course_type, created = LectureType.objects.get_or_create(name=course_type)

        # Figure out day mapping
        try:
            day = ['mandag', 'tirsdag', 'onsdag', 'torsdag', 'fredag'].index(day)
        except ValueError:
            logger.warning("Could not add %s - %s on %s for %s" % (start, end, day, course))
            continue

        start = parse(start).time()
        end = parse(end).time()

        # Rooms:
        rooms = []
        for r in room.split('#'):
            if r.strip():
                r, created = Room.objects.get_or_create(name=r)
                rooms.append(r)

        # Groups:
        groups = set()
        for group in studentset.split('#'):
            match = re.match(u'^([A-ZÆØÅ]+)', group)

            if not match:
                continue

            group, created = Group.objects.get_or_create(name=match.group(1))
            groups.add(group)

        if not groups:
            group, created = Group.objects.get_or_create(name=Group.DEFAULT)
            groups = [group]

        # Weeks
        # FIXME seriosuly this generates way to many db queries...
        weeks = []
        for w in re.split(r',? ', week):
            if '-' in w:
                x, y = w.split('-')
                weeks.extend(range(int(x), int(y)+1))

            elif w.isdigit():
                weeks.append(w)

            else:
                logger.warning("Messed up week '%s' for %s" % (w, course))

        # Lecturer:
        lecturers = []
        for l in lecturer.split('#'):
            if l.strip():
                lecturer, created = Lecturer.objects.get_or_create(
                        name=l.strip())
                lecturers.append(lecturer)

        lecture_kwargs = {
            'course': course,
            'day': day,
            'start': start,
            'end': end,
            'type': course_type,
        }

        if not course_type:
            del lecture_kwargs['type']

        lectures = Lecture.objects.filter(**lecture_kwargs)
        lectures = lectures.exclude(id__in=added_lectures)

        added = False

        for lecture in lectures:
            psql_set = set(lecture.groups.values_list('id', flat=True))
            mysql_set = set(map(lambda g: g.id, groups))

            if psql_set == mysql_set:
                # FIXME need extra check against weeks and rooms
                lecture.rooms = rooms
                lecture.lecturers = lecturers

                added_lectures.append(lecture.id)
                added = True
                break

        if not added:
            lecture = Lecture(**lecture_kwargs)
            lecture.save()

            added_lectures.append(lecture.id)

            # Simply set data since we are saving new lecture
            lecture.groups = groups
            lecture.rooms = rooms
            lecture.lecturers = lecturers

        lecture.start = start
        lecture.end = end
        lecture.save()

        for week in weeks:
            Week.objects.create(lecture=lecture, number=week)

        # FIXME this is backward
        if added:
            logger.debug('%s saved', Lecture.objects.get(pk=lecture.pk))
        else:
            logger.debug('%s added', Lecture.objects.get(pk=lecture.pk))

        skipped -= 1

    to_remove =  Lecture.objects.exclude(id__in=added_lectures). \
            filter(course__semester=semester)

    if matches:
        to_remove = to_remove.filter(course__code__startswith=matches)

    logger.info('%d lectures in source db, %d in destination, diff %d, skipped %d',
            mysql_lecture_count, len(added_lectures), mysql_lecture_count - len(added_lectures), skipped)

    db.close()

    return to_remove

def update_courses(year, semester_type, prefix=None):
    semester, created = Semester.objects.get_or_create(year=year, type=semester_type)

    prefix = prefix or semester.prefix

    db = _connection()
    c = db.cursor()

    if year > 2009 or (year == 2009 and semester_type == Semester.FALL):
        vekt = 'en_navn'
    else:
        vekt = 'vekt'

    c.execute("""SELECT emnekode,emnenavn,%s as vekt FROM %s_fs_emne WHERE
            emnekode NOT LIKE '#%%' AND emnekode NOT LIKE '"%%'""" % (vekt, prefix))

    for code, name, points in c.fetchall():
        code = code.strip().upper()

        if not code:
            continue

        code, version = code.split('-', 2)[:2]
        code = code.strip()
        version = version.strip()

        if not version:
            version = None

        if name[0] in ['"', "'"] and name[0] == name[-1]:
            name = name[1:-1]

        if not re.match(settings.TIMETABLE_VALID_COURSE_NAMES, code):
            logger.info('Skipped invalid course name: %s', code)
            continue

        try:
            course = Course.objects.get(code=code, semester=semester,
                        version=None)
            course.version = version
            created = False

        except Course.DoesNotExist:
            course, created = Course.objects.get_or_create(code=code,
                        semester=semester, version=version)

        if points:
            if vekt == 'en_navn':
                points = points.replace('SP', '')

            course.points = Decimal(points.strip().replace(',', '.'))
        course.name = name
        course.save()

        if created:
            logger.info("Added course %s" % course.code)
        else:
            logger.info("Updated course %s" % course.code)

    db.close()
