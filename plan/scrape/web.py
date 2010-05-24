# encoding: utf-8

# Copyright 2008, 2009 Thomas Kongevold Adamcik
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
from dateutil.parser import parse

from django.conf import settings
from django.db import connection

from plan.common.models import Lecture, Lecturer, Course, Room, LectureType, \
        Semester, Group, Week

logger = logging.getLogger('plan.scrape.web')

is_text = lambda text: isinstance(text, NavigableString)

def to_unicode(value):
    '''Forces NavigableString to unicode'''
    if not isinstance(value, NavigableString):
        return value
    return value.encode('utf-8').decode('utf-8')

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
    results = []
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
            course_time, weeks, room, lecturer, groups  = [], [], [], [], []
            lecture = True
            tr.extract()

            for i, td in enumerate(tr.findAll('td')):
                # Break td loose from rest of table so that any refrences we miss
                # don't cause to big memory problems
                td.extract()

                # Loop over our td's basing our action on the td's index in the tr
                # element.
                if i == 0:
                    if td.get('colspan') == '4':
                        lecture_type = td.findAll(text=is_text)
                        lecture = False
                    else:
                        for t in td.findAll('b')[0].findAll(text=is_text):
                            t.extract()

                            day, period = t.split(' ', 1)
                            start, end = [x.strip() for x in period.split('-')]
                            course_time.append([day, start, end])

                        for week in td.findAll(text=re.compile('^Uke:')):
                            week.extract()
                            for w in week.replace('Uke:', '', 1).split(','):
                                if '-' in w:
                                    x, y = w.split('-')
                                    weeks.extend(range(int(x), int(y)+1))
                                else:
                                    weeks.append(int(w.replace(',', '')))
                elif i == 1:
                    for a in td.findAll('a'):
                        room.extend(a.findAll(text=is_text))
                    for r in room:
                        r.extract()
                elif i == 2:
                    for l in td.findAll(text=is_text):
                        l.extract()

                        lecturer.append(l.replace('&nbsp;', ''))
                elif i == 3:
                    for g in td.findAll(text=is_text):
                        if g.replace('&nbsp;','').strip():
                            g.extract()

                            groups.append(g)

                del td
            del tr

            if lecture:
                results.append({
                    'course': course,
                    'type': map(to_unicode, lecture_type),
                    'time': map(lambda t: map(to_unicode, t),  course_time),
                    'weeks': map(to_unicode, weeks),
                    'room': map(to_unicode, room),
                    'lecturer': map(to_unicode, lecturer),
                    'groups': map(to_unicode, groups),
                })

        del table

    for r in results:
        connection.queries = connection.queries[-5:]

        if r['type']:
            name = r['type'][0]
            lecture_type, created = LectureType.objects.get_or_create(name=name)
        else:
            lecture_type = None
        # Figure out day mapping
        try:
            day = ['Mandag', 'Tirsdag', 'Onsdag', 'Torsdag', 'Fredag']. \
                index(r['time'][0][0])
        except ValueError:
            logger.warning("Could not add %s - %s on %s for %s" % (start, end, day, course))
            continue

        start = parse(r['time'][0][1]).time()
        end = parse(r['time'][0][2]).time()

        lecture, created = Lecture.objects.get_or_create(
            course=r['course'],
            day=day,
            start=start,
            end=end,
            type = lecture_type,
        )

        if not created:
            lecture.rooms.clear()
            lecture.lecturers.clear()
            Week.objects.filter(lecture=lecture).delete()

        if r['room']:
            for room in r['room']:
                room, created = Room.objects.get_or_create(name=room)
                lecture.rooms.add(room)

        if r['groups']:
            for group in r['groups']:
                group, created = Group.objects.get_or_create(name=group)
                lecture.groups.add(group)
        else:
            group, created = Group.objects.get_or_create(name=Group.DEFAULT)
            lecture.groups.add(group)

        for w in r['weeks']:
            Week.objects.create(lecture=lecture, number=w)

        for l in r['lecturer']:
            if l.strip():
                lecturer, created = Lecturer.objects.get_or_create(name=l)
                lecture.lecturers.add(lecturer)

        lecture.save()
        lectures.append(lecture.id)

        logger.info(u'Saved %s' % lecture)

        del lecture
        del r

    to_delete = Lecture.objects.exclude(id__in=lectures).filter(course__semester=semester)

    if matches:
        return to_delete.filter(course__code__startswith=matches)

    return to_delete

