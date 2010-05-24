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

from urllib import urlopen, URLopener, urlencode
from BeautifulSoup import BeautifulSoup, NavigableString

from django.conf import settings

from plan.common.models import Lecture, Course, Semester
from plan.scrape.lectures import (get_day_of_week, get_time, get_weeks,
    process_lectures)

logger = logging.getLogger('plan.scrape.web')

is_text = lambda text: isinstance(text, NavigableString)

def to_unicode(value):
    '''Forces NavigableString to unicode'''
    if not isinstance(value, NavigableString):
        return value
    return value.encode('utf-8').decode('utf-8')

def clean(value):
    return value.replace('&nbsp;', '').strip()

def update_courses(year, semester_type):
    '''Scrape the NTNU website to retrive all available courses'''

    semester, created = Semester.objects.get_or_create(year=year, type=semester_type)

    opener = URLopener()
    opener.addheader('Accept', '*/*')

    courses = []

    for letter in u'ABCDEFGHIJKLMNOPQRSTUVWXYZÆØÅ':
        url = 'http://www.ntnu.no/studieinformasjon/timeplan/%s/?%s' % (
            semester.prefix, urlencode({'bokst': letter.encode('latin1')}))

        logger.info('Retrieving %s', url)

        try:
            html = ''.join(opener.open(url).readlines())
        except IOError, e:
            logger.error('Loading falied')
            continue

        soup = BeautifulSoup(html)

        hovedramme = soup.findAll('div', {'class': 'hovedramme'})[0]

        table = hovedramme.findAll('table', recursive=False)[0]
        table = table.findAll('table')[0]

        table.extract()
        hovedramme.extract()

        for tr in table.findAll('tr'):
            code, name = tr.findAll('a')

            pattern = 'emnekode=(.+?[0-9\-]+)'
            code = re.compile(pattern, re.I|re.L).search(code['href']).group().strip('emnekode=')

            code, version = code.split('-', 2)[:2]
            name = name.contents[0]

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

        table = None

        for number in versions_to_try:
            final_url = '%s-%s' % (url, number)

            logger.info('Retrieving %s', final_url)

            html = ''.join(urlopen(final_url).readlines())
            main = BeautifulSoup(html).findAll('div', 'hovedramme')[0]

            if not main.findAll('h1', text=lambda t: course.code in t):
                main.extract()
                del html
                del main
                continue

            table = main.findAll('table')[1]

            # Try and get rid of stuff we don't need.
            table.extract()
            main.extract()
            del html
            del main

            break

        if not table:
            continue

        lecture_type = None
        for tr in table.findAll('tr')[1:-1]:
            weeks, rooms, lecturers, groups  = [], [], [], []
            day, start, end = None, None, None
            lecture = True
            tr.extract()

            for i, td in enumerate(tr.findAll('td')):
                if i == 0:
                    if td.get('colspan') == '4':
                        lecture_type = clean(td.findAll(text=is_text)[0])
                        lecture = False
                    else:
                        time = td.findAll('b')[0].findAll(text=is_text)[0]
                        day, period = time.split(' ', 1)
                        start, end = period.split('-')

                        day = get_day_of_week(day)
                        start = get_time(start)
                        end = get_time(end)

                        for week in td.findAll(text=re.compile('^Uke:')):
                            week = week.replace('Uke:', '', 1).split(',')
                            weeks.extend(get_weeks(week))
                elif i == 1:
                    for a in td.findAll('a'):
                        for room in a.findAll(text=is_text):
                            rooms.append(clean(room))
                elif i == 2:
                    for lecturer in td.findAll(text=is_text):
                        lecturers.append(clean(lecturer))
                elif i == 3:
                    for group in td.findAll(text=is_text):
                        groups.append(clean(group))

            if lecture:
                if day is None or not start or not end:
                    logger.waring('Lecture time is wrong for %s: day %s start %s end %s', course, day, start, end)
                    continue

                data.append({
                    'course': course,
                    'type': clean(lecture_type),
                    'day': day,
                    'start': start,
                    'end': end,
                    'weeks': filter(bool, weeks),
                    'rooms': filter(bool, map(to_unicode, rooms)),
                    'lecturers': filter(bool, map(to_unicode, lecturers)),
                    'groups': filter(bool, map(to_unicode, groups)),
                })

            del tr
        del table

    added_lectures = process_lectures(data)
    to_delete = Lecture.objects.exclude(id__in=added_lectures)
    to_delete = to_delete.filter(course__semester=semester)

    if matches:
        return to_delete.filter(course__code__startswith=matches)

    return to_delete

