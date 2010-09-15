# encoding: utf-8

# Copyright 2008, 2009, 2010 Thomas Kongevold Adamcik
# 2009 IME Faculty Norwegian University of Science and Technology

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

import re
import logging
from urllib import urlencode
from lxml.html import parse

from django.conf import settings

from plan.common.models import Lecture, Course, Semester
from plan.scrape.lectures import (get_day_of_week, get_time, get_weeks,
    process_lectures)

logger = logging.getLogger('plan.scrape.web')

def update_courses(year, semester_type):
    '''Scrape the NTNU website to retrive all available courses'''

    semester, created = Semester.objects.get_or_create(year=year, type=semester_type)

    courses = []

    for letter in u'ABCDEFGHIJKLMNOPQRSTUVWXYZÆØÅ':
        url = 'http://www.ntnu.no/studieinformasjon/timeplan/%s/?%s' % (
            semester.prefix, urlencode({'bokst': letter.encode('latin1')}))

        logger.info('Retrieving %s', url)

        try:
            root = parse(url).getroot()
        except IOError, e:
            logger.error('Loading falied')
            continue

        for tr in root.cssselect('.hovedramme table table tr'):
            code, name = tr.cssselect('a')

            pattern = 'emnekode=(.+?[0-9\-]+)'
            code = re.compile(pattern, re.I|re.L).search(code.attrib['href']).group(1)

            code, version = code.split('-', 2)[:2]
            name = name.text_content()

            if name.endswith('(Nytt)'):
                name = name.rstrip('(Nytt)')

            if not re.match(settings.TIMETABLE_VALID_COURSE_NAMES, code):
                logger.info('Skipped invalid course name: %s', code)
                continue

            courses.append((code, name, version))

    for code, name, version in courses:
        code = code.strip().upper()
        name = name.strip()
        version = version.strip()

        if not version:
            version = None

        try:
            course = Course.objects.get(code=code, semester=semester, version=None)
            course.version = version
        except Course.DoesNotExist:
            course, created = Course.objects.get_or_create(code=code, semester=semester, version=version)

        if course.name != name:
            course.name = name

        logger.info("Saved course %s" % course.code)
        course.save()

    return courses

def update_lectures(year, semester_type, matches=None, prefix=None):
    '''Retrive all lectures for a given course'''

    semester, created = Semester.objects.get_or_create(year=year, type=semester_type)

    prefix = prefix or semester.prefix
    data = []
    lectures = []

    courses = Course.objects.filter(semester=semester).distinct().order_by('code')

    if matches:
        courses = courses.filter(code__startswith=matches)

    for course in courses:
        url  = 'http://www.ntnu.no/studieinformasjon/timeplan/%s/?%s' % \
                (prefix, urlencode({'emnekode': course.code.encode('latin1')}))

        if course.version:
            versions_to_try = [course.version]
        else:
            versions_to_try = [1, 2, 3, 4]

        for number in versions_to_try:
            final_url = '%s-%s' % (url, number)

            logger.info('Retrieving %s', final_url)

            root = parse(final_url).getroot()

            for h1 in root.cssselect(u'.hovedramme h1'):
                if course.code in h1.text_content():
                    table = root.cssselect('.hovedramme table')[1];
                    break

        if table is None:
            logger.warning("Couldn't load any lecture info for %s", course.code)
            continue

        lecture_type = None
        for tr in table.cssselect('tr')[1:-1]:
            weeks, rooms, lecturers, groups  = [], [], [], []
            day, start, end = None, None, None
            lecture = True

            for i, td in enumerate(tr.cssselect('td')):
                if i == 0:
                    if td.attrib.get('colspan', 1) == '4':
                        lecture_type = td.text_content().strip()
                        lecture = False
                    else:
                        time = td.cssselect('b')[0].text_content().strip()
                        day, period = time.split(' ', 1)
                        start, end = period.split('-')

                        day = get_day_of_week(day)
                        start = get_time(start)
                        end = get_time(end)

                        week = re.match('.*Uke: (.+)', td.text_content()).group(1).split(',')
                        weeks.extend(get_weeks(week))
                elif i == 1:
                    for a in td.cssselect('a'):
                        rooms.append(a.text_content().strip())
                elif i == 2:
                    lecturers.append(td.text.strip())
                    for br in td:
                        lecturers.append(br.tail.strip())
                elif i == 3:
                    for group in td.cssselect('span'):
                        groups.append(group.text_content().strip())

            if lecture:
                if day is None or not start or not end:
                    logger.warning("Could not add %s - %s on %s for %s" % (start, end, day, course))
                    continue

                data.append({
                    'course': course,
                    'type': lecture_type,
                    'day': day,
                    'start': start,
                    'end': end,
                    'weeks': filter(bool, weeks),
                    'rooms': filter(bool, rooms),
                    'lecturers': filter(bool, lecturers),
                    'groups': filter(bool, groups),
                })

    added_lectures = process_lectures(data)
    to_delete = Lecture.objects.exclude(id__in=added_lectures)
    to_delete = to_delete.filter(course__semester=semester)

    if matches:
        return to_delete.filter(course__code__startswith=matches)

    return to_delete

