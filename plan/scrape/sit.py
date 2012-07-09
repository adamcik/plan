# This file is part of the plan timetable generator, see LICENSE for details.

import logging
import lxml.html
import urllib

from plan.common.models import Course, Semester
from plan.scrape import utils

logger = logging.getLogger('scrape.sit')

SEMESTER_NAMES = {Semester.FALL: 'Autumn',
                  Semester.SPRING: 'Spring'}


# TODO(adamcik): this is broken since tapir merged.


def update_syllabus(year, semester, match=None):
    courses = Course.objects.filter(semester__type=semester,
        semester__year__exact=year)

    if match:
        courses = courses.filter(code__startswith=match)

    for course in courses.all():
        url = 'http://sittapir.sit.no/pensum/NTNU/%s/%s/%s' % (
            year, SEMESTER_NAMES[semester],
            urllib.quote(course.code.encode('utf-8')))

        logger.info('Retrieving %s', url)
        try:
            root = lxml.html.fromstring(utils.cached_urlopen(url))
        except IOError, e:
            logger.warning('Parse failed for %s: %s', course.code, e)
            continue

    for course in courses.filter(syllabus=''):
        course.syllabus = base_url % course.code
        course.save()

        logger.info(course.syllabus)
