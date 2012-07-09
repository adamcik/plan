# encoding: utf-8

# This file is part of the plan timetable generator, see LICENSE for details.

import logging
import re
from decimal import Decimal

from django.conf import settings
from django.db import connections

from plan.common.models import Course, Lecture, Semester
from plan.scrape.lectures import get_day_of_week, process_lectures, get_time, get_weeks

logger = logging.getLogger('scrape.db')

# TODO(adamcik): scapring in general, switch to config that determines which
#                code to use instead of flags.

# TODO(adamcik): switch to passing in semester
# TODO(adamcik): prefix should be contained to ntnu code, i.e. remove it from
#                this interface.
def update_lectures(year, semester_type, prefix=None, matches=None):
    '''Retrive all lectures for a given course'''

    semester, created = Semester.objects.get_or_create(year=year, type=semester_type)

    prefix = prefix or semester.prefix

    logger.debug('Using prefix: %s', prefix)

    c = connections['ntnu'].cursor()

    query = ("SELECT emnekode, typenavn, dag, start, slutt, uke, "
             "romnavn, larer, aktkode FROM {0}_timeplan").format(prefix)
    params = []

    if matches:
        logger.info('Limiting to %s*', matches)

        query += ' AND emnekode LIKE %s'
        params.append(matches + '%')

    query += ' ORDER BY emnekode, dag, start, slutt, uke, romnavn, aktkode'
    c.execute(query, *params)

    data = []
    added_lectures = []
    mysql_lecture_count = 0
    skipped = 0

    lectures = Lecture.objects.filter(course__semester=semester)

    if matches:
        lectures = lectures.filter(course__code__startswith=matches)

    for row in c.fetchall():
        (code, lecture_type, db_day, db_start,
         db_end, week, room,lecturer, groupcode) = row

        # TODO(adamcik): replace this with regexp to extract code. current
        #                regexp in settings should probably be replaced with a
        #                hardcoded helper in the ntnu module.
        if not (code and code.strip() and '-' in code):
            continue

        mysql_lecture_count += 1

        code = code.rsplit('-', 1)[0].upper()

        if not re.match(settings.TIMETABLE_VALID_COURSE_NAMES, code):
            logging.info('Skipped %s', code)
            skipped += 1
            continue

        # Get course
        # TODO(adamcik): simply put course code in data
        try:
            course = Course.objects.get(code=code, semester=semester)
        except Course.DoesNotExist:
            logger.warning("Cout not add %s - %s on %s for %s as course does"
                " not exist for this semester", db_start, db_end, db_day, code)
            continue

        # TODO(adamciK): move these helpers to common scrape code or to a ntnu
        #                module.
        day = get_day_of_week(db_day)
        start = get_time(db_start)
        end = get_time(db_end)

        if day is None or start is None or end is None:
            logger.warning("Could not add %s - %s on %s for %s" % (db_start, db_end, db_day, course))
            skipped += 1
            continue

        rooms = room.split('#')
        weeks = get_weeks(re.split(r',? ', week))
        lecturers = lecturer.split('#')

        groups = set()

        # TODO(adamcik): memoize this fetch?
        query = ("SELECT DISTINCT asp.studieprogramkode "
                 "FROM {0}_akt_studieprogram asp, studieprogram sp "
                 "WHERE asp.studieprogramkode=sp.studieprogram_kode "
                 "AND asp.aktkode = %s").format(prefix)

        c2 = connections['ntnu'].cursor()
        c2.execute(query, groupcode.encode('utf8'))
        for row in c2.fetchall():
            groups.add(row[0])

        data.append({
            'course': course,
            'type': lecture_type,
            'day': day,
            'start': start,
            'end': end,
            'weeks': filter(bool, weeks),
            'rooms': filter(bool, rooms),
            'lecturers': filter(bool, lecturers),
            'groups': filter(bool, groups),
        })

    # TODO(adamcik): we should be returning data - i.e. time to invert control
    added_lectures = process_lectures(data)
    to_delete = Lecture.objects.exclude(id__in=added_lectures)
    to_delete = to_delete.filter(course__semester=semester)

    if matches:
        return to_delete.filter(course__code__startswith=matches)

    logger.info('%d lectures in source db, %d in destination, diff %d, skipped %d',
            mysql_lecture_count, len(added_lectures), mysql_lecture_count - len(added_lectures), skipped)

    return to_delete

def update_courses(year, semester_type, prefix=None):
    semester, created = Semester.objects.get_or_create(year=year, type=semester_type)

    prefix = prefix or semester.prefix

    c = connections['ntnu'].cursor()

    # Handle changes in database over time:
    if year > 2009 or (year == 2009 and semester_type == Semester.FALL):
        vekt = 'en_navn'
    else:
        vekt = 'vekt'

    query = ("SELECT emnekode, emnenavn, {0} as vekt "
             "FROM {1}_fs_emne").format(vekt, prefix)
    c.execute(query)

    for code, name, points in c.fetchall():
        code = code.strip().upper()

        if not code or '-' not in code:
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

        # TODO(adamcik): I think this is a hack to remove courses that are
        #                missing version, can probably be removed.
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
            points = points.strip('-\n\r\t ')
            course.points = Decimal(points.replace(',', '.'))
        course.name = name
        course.save()

        if created:
            logger.info("Added course %s", course.code)
        else:
            logger.info("Updated course %s", course.code)
