# This file is part of the plan timetable generator, see LICENSE for details.

import logging

from plan.common.models import Course, Semester


class Scraper(object):
    def __init__(self, semester, options):
        self.semester = semester
        self.options = options

    def fetch(self, match=None):
        raise NotImplementedError

    def run(self):
        return self.fetch()


class CourseScraper(Scraper):
    def run(self):
        extra_fields = ('name', 'url', 'syllabus', 'points')

        semester, created = Semester.objects.get_or_create(
            year=self.semester.year, type=self.semester.type)

        for data in self.fetch(match=self.options['match']):
            defaults = {}
            for field in extra_fields:
                if field in data:
                    defaults[field] = data[field]

            course, created = Course.objects.get_or_create(
                code=data['code'], version=data['version'],
                semester=semester, defaults=defaults)

            updated = False
            for field in extra_fields:
                if field in data and not getattr(course, field):
                    setattr(course, field, data[field])
                    updated = True

            if created:
                logging.info('Added course %s', course.code)
            elif updated:
                logging.info('Updated course %s', course.code)
            else:
                logging.debug('No changes for course %s', course.code)

        return []  # Never delete courses in the system.
