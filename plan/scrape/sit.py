# This file is part of the plan timetable generator, see LICENSE for details.

import logging
import urllib

from lxml.html import fromstring

from plan.common.models import Course, Semester
from plan.scrape import fetch_url

logger = logging.getLogger('scrape.sit')

def update_syllabus(year, semester, match=None):
    courses = Course.objects.filter(semester__type=semester,
        semester__year__exact=year)

    if match:
        courses = courses.filter(code__startswith=match)

    for course in courses.all():
        url = 'http://sittapir.sit.no/pensum/NTNU/%s/%s/%s' % (
            year, semester_mapping[semester],
            urllib.quote(course.code.encode('utf-8')))

        try:
            html = fetch_url(url)
            root = fromstring(html)
        except IOError, e:
            logger.warning('Parse failed for %s: %s', course.code, e)
            continue

    for course in courses.filter(syllabus=''):
        course.syllabus = base_url % course.code
        course.save()

        logger.info(course.syllabus)
