# encoding: utf-8

# This file is part of the plan timetable generator, see LICENSE for details.

import logging
import re
from decimal import Decimal

from django.conf import settings
from django.db import connections

from plan.common.models import Course, Lecture, Semester
from plan.scrape import utils
from plan.scrape.lectures import process_lectures

logger = logging.getLogger('scrape.db')

# TODO(adamcik): scapring in general, switch to config that determines which
#                code to use instead of flags.

# TODO(adamcik): switch to passing in semester
# TODO(adamcik): switch to passing in lectures that match our filter.
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

    for row in c.fetchall():
        (raw_code, raw_type, raw_day, raw_start, raw_end,
         raw_weeks, raw_rooms, raw_lecturers, raw_group) = row

        code, version = utils.parse_course_code(raw_code)

        if not code:
            logging.info('Skipped %s', raw_code)
            skipped += 1
            continue

        mysql_lecture_count += 1

        # TODO(adamcik): simply put course code in data?
        try:
            course = Course.objects.get(code=code, semester=semester)
        except Course.DoesNotExist:
            logger.warning(
                "Cout not add %s - %s on %s for %s as course does not exist "
                "for this semester", raw_start, raw_end, raw_day, code)
            continue

        day = utils.parse_day_of_week(raw_day)
        start = utils.parse_time(raw_start)
        end = utils.parse_time(raw_end)

        if day is None or start is None or end is None:
            logger.warning("Could not add %s - %s on %s for %s",
                           raw_start, raw_end, raw_day, course)
            skipped += 1
            continue

        rooms = raw_rooms.split('#')
        weeks = utils.parse_weeks(raw_weeks)
        lecturers = raw_lecturers.split('#')

        groups = set()

        # TODO(adamcik): memoize this fetch?
        query = ("SELECT DISTINCT asp.studieprogramkode "
                 "FROM {0}_akt_studieprogram asp, studieprogram sp "
                 "WHERE asp.studieprogramkode=sp.studieprogram_kode "
                 "AND asp.aktkode = %s").format(prefix)

        c2 = connections['ntnu'].cursor()
        c2.execute(query, raw_group.encode('utf8'))
        for row in c2.fetchall():
            groups.add(row[0])

        # TODO(adamcik): figure out if we can get rid of the filter hack.
        data.append({
            'course': course,
            'type': raw_type,
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

    # TODO(adamcik): create cursor() helper in module.
    cursor = connections['ntnu'].cursor()
    cursor.execute("SELECT emnekode, emnenavn FROM {0}_fs_emne".format(prefix))

    # TODO(adamcik): figure out how to get course credits.
    for raw_code, raw_name in cursor.fetchall():
        code, version = utils.parse_course_code(raw_code)

        if not code:
            logger.info('Skipped invalid course name: %s', raw_code)
            continue

        # TODO(adamcik): add constraint for code+semester to prevent multiple
        #                versions by mistake
        course, created = Course.objects.get_or_create(
            code=code, semester=semester, version=version)
        course.name = raw_name
        course.save()

        if created:
            logger.info("Added course %s", course.code)
        else:
            logger.info("Updated course %s", course.code)

    # TODO(adamcik): return data with course code and name.
