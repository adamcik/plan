# encoding: utf-8

import logging
import re
from decimal import Decimal
from dateutil.parser import parse

from django.db import transaction
from django.conf import settings

from plan.common.models import Course, Lecture, Lecturer, Semester, Group, \
        Type, Week, Room

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
            SELECT emnekode,typenavn,dag,start,slutt,uke,romnavn,larer,aktkode
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
        lectures = lectures.filter(course__name__startswith=matches)

    for l in lectures:
        l.rooms.clear()
        l.lecturers.clear()
        Week.objects.filter(lecture=l).delete()

    for row in c.fetchall():
        code, course_type, day, start, end, week, room, lecturer, groupcode = row
        if not code.strip():
            continue

        mysql_lecture_count += 1
        skipped += 1

        # Remove -1 etc. from course code
        code = '-'.join(code.split('-')[:-1]).upper()

        if not re.match(settings.TIMETABLE_VALID_COURSE_NAMES, code):
            continue 

        # Get and or update course
        course, created = Course.objects.get_or_create(name=code)
        course.semesters.add(semester)

        # Load or create type:
        if course_type:
            course_type, created = Type.objects.get_or_create(name=course_type)

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
        groups = []
        c2 = db.cursor()
        c2.execute("""
                SELECT DISTINCT asp.studieprogramkode
                FROM %s_akt_studieprogram asp,studieprogram sp
                WHERE asp.studieprogramkode=sp.studieprogram_kode
                AND asp.aktkode = %%s
            """ % prefix, groupcode)
        for group in c2.fetchall():
            group, created = Group.objects.get_or_create(name=group[0])
            groups.append(group)

        if not groups:
            group, created = Group.objects.get_or_create(name=Group.DEFAULT)
            groups = [group]

        # Weeks
        # FIXME seriosuly this generates way to many db queries...
        weeks = []
        for w in re.split(r',? ', week):
            if '-' in w:
                x, y = w.split('-')
                for i in range(int(x), int(y)+1):
                    w2 = Week.objects.get(number=i)
                    weeks.append(w2)
            elif w.isdigit():
                w2 = Week.objects.get(number=w)
                weeks.append(w2)
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
            'semester': semester,
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
                lecture.weeks = weeks
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
            lecture.weeks = weeks
            lecture.lecturers = lecturers

        lecture.start = start
        lecture.end = end
        lecture.save()

        # FIXME this is backward
        if added:
            logger.debug('%s saved', Lecture.objects.get(pk=lecture.pk))
        else:
            logger.debug('%s added', Lecture.objects.get(pk=lecture.pk))

        skipped -= 1

    to_remove =  Lecture.objects.exclude(id__in=added_lectures). \
            filter(course__semester=semester)

    if matches:
        to_remove = to_remove.filter(course__name__startswith=matches)

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

    c.execute("""SELECT emnekode,emnenavn,%s as vekt FROM %s_fs_emne WHERE emnekode
            NOT LIKE '#%%'""" % (vekt, prefix))

    for code, name, points in c.fetchall():
        if not code.strip():
            continue

        code = ''.join(code.split('-')[:-1]).upper().strip()

        if name[0] in ['"', "'"] and name[0] == name[-1]:
            name = name[1:-1]

        if not re.match(settings.TIMETABLE_VALID_COURSE_NAMES, name):
            logger.info('Skipped invalid course name: %s', name)
            continue 

        course, created = Course.objects.get_or_create(name=code)

        if points:
            if vekt == 'en_navn':
                points = points.replace('SP', '')

            course.points = Decimal(points.strip().replace(',', '.'))
        course.full_name = name
        course.save()

        if created:
            logger.info("Added course %s" % course.name)
        else:
            logger.info("Updated course %s" % course.name)

    db.close()
