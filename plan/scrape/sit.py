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

from plan.common.models import Course, Semester

logger = logging.getLogger('scrape.sit')

def update_syllabus(year, semester, match=None):
    courses = Course.objects.filter(semester__type=semester,
        semester__year__exact=year)

    if match:
        courses = courses.filter(code__startswith=match)

    base_url = 'http://sittapir.sit.no/sok.aspx?q=%s'

    for course in courses.filter(syllabus=''):
        course.syllabus = base_url % course.code
        course.save()

        logger.info(course.syllabus)
