# encoding: utf-8

# This file is part of the plan timetable generator, see LICENSE for details.

import logging

from plan.common.models import Course, Lecture, Semester
from plan.scrape import base
from plan.scrape import ntnu
from plan.scrape import utils
from plan.scrape import fetch


class Courses(base.CourseScraper):
    def scrape(self):
        prefix = ntnu.prefix(self.semester)
        query = "SELECT emnekode, emnenavn FROM %s_fs_emne" % prefix

        for row in fetch.sql('ntnu', query):
            code, version = ntnu.parse_course(row.emnekode)
            if not code:
                logging.warning('Skipped invalid course name: %s', row.emnekode)
                continue

            yield {'code': code,
                   'name': row.emnenavn,
                   'version': version,
                   'url': 'http://www.ntnu.no/studier/emner/%s' % code}

    def delete(self, qs):
        logging.warning('This scraper only knows about courses in the '
                        'timetable db, not deleting any unknown courses. '
                        'Note that the scraper is aslo oblivious about if a '
                        'course is still being taught and/or assesed, so it '
                        'tends to add to much.')


class Lectures(base.LectureScraper):
    def scrape(self):
        prefix = ntnu.prefix(self.semester)
        groups = {}

        courses = Course.objects.filter(semester=self.semester)
        courses = dict((c.code, c) for c in courses)

        query = ('SELECT aktkode, studieprogramkode FROM '
                 '%s_akt_studieprogram') % prefix

        for row in fetch.sql('ntnu', query):
            groups.setdefault(row.aktkode, set()).add(row.studieprogramkode)

        query = ('SELECT emnekode, typenavn, dag, start, slutt, uke, romnr, '
                 'romnavn, larer, aktkode FROM %s_timeplan ORDER BY emnekode, '
                 'dag, start, slutt, uke, romnavn, aktkode') % prefix

        for row in fetch.sql('ntnu', query):
            code, version = ntnu.parse_course(row.emnekode)
            if not code:
                logging.warning('Skipped invalid course name: %s', row.emnekode)
                continue
            elif code not in courses:
                logging.debug("Unknown course %s.", code)
                continue

            yield {'course': courses[code],
                   'type': row.typenavn,
                   'day':  utils.parse_day_of_week(row.dag),
                   'start': utils.parse_time(row.start),
                   'end':  utils.parse_time(row.slutt),
                   'weeks': utils.parse_weeks(row.uke),
                   'rooms': zip(utils.split(row.romnr, '#'),
                                utils.split(row.romnavn, '#')),
                   'lecturers': utils.split(row.larer, '#'),
                   'groups': groups.get(row.aktkode, set())}
