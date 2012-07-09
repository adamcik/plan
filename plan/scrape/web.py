# encoding: utf-8

# This file is part of the plan timetable generator, see LICENSE for details.

import logging
import lxml.html
import re
import urllib

from django.conf import settings

from plan.common.models import Lecture, Course, Semester
from plan.scrape import utils
from plan.scrape.lectures import process_lectures

logger = logging.getLogger('plan.scrape.web')

def update_courses(year, semester_type):
    '''Scrape the NTNU website to retrive all available courses'''

    semester, created = Semester.objects.get_or_create(year=year, type=semester_type)

    courses = []

    for letter in u'ABCDEFGHIJKLMNOPQRSTUVWXYZÆØÅ':
        query = {'bokst': letter.encode('latin1')}
        url = 'http://www.ntnu.no/studieinformasjon/timeplan/{0}/?{1}'.format(
            semester.prefix, urllib.urlencode(query))

        logger.info('Retrieving %s', url)
        try:
            root = lxml.html.fromstring(utils.cached_urlopen(url))
        except IOError, e:
            logger.error('Loading falied')
            continue

        for tr in root.cssselect('.hovedramme table table tr'):
            code_link, name_link = tr.cssselect('a')

            code_href = code_link.attrib['href']
            code_re = re.compile('emnekode=([^&]+)', re.I|re.L)
            raw_code = code_re.search(code_href).group(1)

            code, version = utils.parse_course_code(raw_code)
            if not code:
                logger.info('Skipped invalid course name: %s', code)
                continue

            # Strip out noise in course name.
            name = re.search(r'(.*)(\(Nytt\))?', name_link.text_content()).group(1)

            courses.append({'code': code,
                            'name': name.strip(),
                            'version': version,
                            'points': None})

    # TODO(adamcik): convert this to generic course handling code.
    for data in courses:
        try:
            course = Course.objects.get(code=data['code'], semester=semester, version=None)
            course.version = data['version']
        except Course.DoesNotExist:
            course, created = Course.objects.get_or_create(
                code=data['code'], semester=semester, version=data['version'])
        course.name = data['name']
        course.save()

        logger.info("Saved course %s" % course.code)

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
        query = {'emnekode': course.code.encode('latin1')}
        url = 'http://www.ntnu.no/studieinformasjon/timeplan/{0}/?{1}'.format(
            prefix, urllib.urlencode(query))

        if course.version:
            versions_to_try = [course.version]
        else:
            versions_to_try = [1, 2, 3, 4]

        table = None
        for number in versions_to_try:
            final_url = '%s-%s' % (url, number)

            logger.info('Retrieving %s', final_url)
            try:
                root = lxml.html.fromstring(utils.cached_urlopen(final_url))
            except IOError:
                continue

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
                        raw_day, period = time.split(' ', 1)
                        raw_start, raw_end = period.split('-')

                        day = utils.parse_day_of_week(raw_day)
                        start = utils.parse_time(raw_start)
                        end = utils.parse_time(raw_end)

                        raw_weeks = re.match('.*Uke: (.+)', td.text_content()).group(1)
                        weeks.extend(utils.parse_weeks(raw_weeks))
                elif i == 1:
                    for a in td.cssselect('a'):
                        rooms.append(a.text_content().strip())
                elif i == 2:
                    lecturers.append(td.text.strip())
                    for nl in td:
                        lecturers.append(nl.tail.strip())
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

