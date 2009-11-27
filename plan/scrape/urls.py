# Copyright 2008, 2009 Thomas Kongevold Adamcik

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
import re
from urllib2 import urlopen, HTTPError

from plan.common.models import Course

URL_MAP = {
    'IT': lambda c: 'http://www.idi.ntnu.no/emner/%s' % c.code.lower(),
    'TDT': lambda c: 'http://www.idi.ntnu.no/emner/%s' % c.code.lower(),

    'TFE': lambda c: 'http://www.iet.ntnu.no/courses/%s' % c.code.lower(),
    'TTT': lambda c: 'http://www.iet.ntnu.no/courses/%s' % c.code.lower(),

    'MA': lambda c: 'http://www.math.ntnu.no/emner/%s' % c.code.upper(),
    'ST': lambda c: 'http://www.math.ntnu.no/emner/%s' % c.code.upper(),
    'TMA': lambda c: 'http://www.math.ntnu.no/emner/%s' % c.code.upper(),
}

logger = logging.getLogger('plan.scrape.web')

def update_urls(year, semester_type):
    courses = Course.objects.filter(semester__year__exact=year)
    courses = courses.filter(semester__type=semester_type)
    courses = courses.filter(url='')

    for course in courses:
        match = re.match(r'^([A-Z]+)', course.code.upper())

        if not match:
            continue

        if match.group(1) not in URL_MAP:
            continue

        try:
            url = URL_MAP[match.group(1)](course)

            logger.debug('Tyring %s for %s', url, course.code)

            urlopen(url)

            logger.info('Setting %s for %s', url, course.code)

            course.url = url
            course.save()
        
        except HTTPError:
            pass
