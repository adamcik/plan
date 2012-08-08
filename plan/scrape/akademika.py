# This file is part of the plan timetable generator, see LICENSE for details.

import json
import logging
import urllib

from plan.common.models import Course, Semester
from plan.scrape import fetch

logger = logging.getLogger('scrape.akademika')


def update_syllabus(year, semester, match=None):
    courses = Course.objects.filter(semester__type=semester,
        semester__year__exact=year)

    if match:
        courses = courses.filter(code__startswith=match)

    for course in courses.all():
        url = 'http://www.akademika.no/pensumlister/autocomplete/%s' % (
            urllib.quote(course.code.encode('utf-8')))

        try:
            data = json.loads(fetch.plain(url))
        except IOError, e:
            logger.warning('Parse failed for %s: %s', course.code, e)
            continue

        if not data:
            continue

        if len(data.keys()) != 1:
            logger.warning('More than one match for %s', course.code)
            continue

        course.syllabus = 'http://www.akademika.no/node/%s' % (data.keys()[0])
        course.save()
        logger.info('%s: %s', course.code, course.syllabus)
