# encoding: utf-8

# This file is part of the plan timetable generator, see LICENSE for details.

import logging

from django.db import connections

from plan.common.models import Course, Lecture, Semester
from plan.scrape import base
from plan.scrape import ntnu
from plan.scrape import utils


class Courses(base.CourseScraper):
    def scrape(self):
        prefix = ntnu.prefix(self.semester)
        cursor = connections['ntnu'].cursor()
        cursor.execute("SELECT emnekode, emnenavn FROM %s_fs_emne" % prefix)

        for raw_code, raw_name in cursor.fetchall():
            code, version = ntnu.parse_course(raw_code)
            if not code:
                logging.warning('Skipped invalid course name: %s', raw_code)
                continue

            yield {'code': code,
                   'name': raw_name,
                   'version': version,
                   'url': 'http://www.ntnu.no/studier/emner/%s' % code}

    def prepare_delete(self, pks):
        logging.warning('This scraper only knows about courses in the')
        logging.warning('timetable db, not deleting any unknown courses.')
        logging.warning('Note that the scraper is aslo oblivious about if a')
        logging.warning('course is still being taught and/or assesed, so it')
        logging.warning('tends to add to much.')
        return self.queryset().none()


class Lectures(base.LectureScraper):
    def scrape(self):
        prefix = ntnu.prefix(self.semester)
        cursor = connections['ntnu'].cursor()
        groups = {}

        courses = Course.objects.filter(semester=self.semester)
        courses = dict((c.code, c) for c in courses)

        # TODO(adamcik): start getting group names not just short names?
        cursor.execute(('SELECT aktkode, studieprogramkode '
                        'FROM %s_akt_studieprogram') % prefix)

        for activity, group in cursor.fetchall():
            groups.setdefault(activity, set()).add(group)

        cursor.execute(('SELECT emnekode, typenavn, dag, start, slutt, uke, '
                        'romnr, romnavn, larer, aktkode FROM %s_timeplan ORDER BY '
                        'emnekode, dag, start, slutt, uke, romnavn, aktkode') %
                        prefix)

        for row in cursor.fetchall():
            (raw_code, lecture_type, day, start, end, weeks,
             roomcodes, roomnames, lecturers, activity) = row

            code, version = ntnu.parse_course(raw_code)
            if not code:
                logging.warning('Skipped invalid course name: %s', raw_code)
                continue
            elif code not in courses:
                logging.debug("Unknown course %s.", code)
                continue

            yield {'course': courses[code],
                   'type': lecture_type,
                   'day':  utils.parse_day_of_week(day),
                   'start': utils.parse_time(start),
                   'end':  utils.parse_time(end),
                   'weeks': utils.parse_weeks(weeks),
                   'rooms': utils.split(rooms, '#'),
                   'lecturers': utils.split(lecturers, '#'),
                   'groups': groups.get(activity, set())}
