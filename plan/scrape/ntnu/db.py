# encoding: utf-8

# This file is part of the plan timetable generator, see LICENSE for details.

import logging

from django.db import connections

from plan.common.models import Course, Lecture, Semester
from plan.scrape import ntnu
from plan.scrape import base


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

    def prepare_delete(self, qs, pks):
        return qs.none()

    def log_instructions(self):
        logging.warning('This scraper only knows about courses in the')
        logging.warning('timetable db, not deleting any unknown courses.')
        logging.warning('Note that the scraper is aslo oblivious about if a')
        logging.warning('course is still being taught and/or assesed, so it')
        logging.warning('tends to add to much.')
