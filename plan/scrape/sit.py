# Copyright 2010 Thomas Kongevold Adamcik

# This file is part of Plan.
#
# Plan is free software: you can redistribute it and/or modify
# it under the terms of the Affero GNU General Public License as
# published by the Free Software Foundation, either version 3 of
# the License, or (at your option) any later version.
#
# Plan is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# Affero GNU General Public License for more details.
#
# You should have received a copy of the Affero GNU General Public
# License along with Plan.  If not, see <http://www.gnu.org/licenses/>.

import logging
import urllib
from lxml.html import parse

from plan.common.models import Course, Semester

logger = logging.getLogger('scrape.sit')

semester_mapping = {
    Semester.FALL: 'Autumn',
    Semester.SPRING: 'Spring',
}

def update_syllabus(year, semester, match=None):
    courses = Course.objects.filter(semester__type=semester,
        semester__year__exact=year)

    if match:
        courses = courses.filter(code__startswith=match)

    for course in courses.filter(syllabus=''):
        url = 'http://sittapir.sit.no/pensum/NTNU/%s/%s/%s' % (
            year, semester_mapping[semester],
            urllib.quote(course.code.encode('utf-8')))

        logger.info('Trying %s', url)

        try:
            root = parse(url).getroot()
        except IOError, e:
            logger.warning('Parse failed for %s: %s', course.code, e)
            continue

        if not root.cssselect('#pensumliste .produkter_wrapper'):
            logger.warning("Didn't find any tables in results for %s", course.code)
            continue

        course.syllabus = url
        course.save()
