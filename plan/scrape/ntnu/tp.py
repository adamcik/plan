# This file is part of the plan timetable generator, see LICENSE for details.

import json
import re

from plan.common.models import Semester
from plan.scrape import base
from plan.scrape import fetch
from plan.scrape import utils


class Courses(base.CourseScraper):
    def scrape(self):
        if self.semester == Semester.SPRING:
            year = self.semester.year - 1
        else:
            year = self.semester.year

        url = 'https://www.ntnu.no/studier/emner/%s/2018'

        for course, name in fetch_courses(self.semester).items():
            yield {
                'code': course,
                'name': name,
                'version': 1,
                'url': url % course,
            }


class Lectures(base.LectureScraper):
    def scrape(self):

        for c in self.course_queryset():
            result = fetch_course_lectures(self.semester, c)

            if 'data' not in result or not result['data']:
                continue

            for methods in result['data'].values():
                for method in methods:
                    for sequence in method['eventsequences']:
                        current = None

                        for e in sequence['events']:
                            tmp = {
                                'day': utils.parse_date(e['dtstart']).weekday(),
                                'start': utils.parse_time(e['dtstart']),
                                'end':  utils.parse_time(e['dtend']),
                                'rooms': [(r['id'], r['roomname'], None) for r in e.get('room', [])],
                                'groups': process_groups(e.get('studentgroups', [])),
                            }

                            if not current:
                                current = {
                                    'course': c,
                                    'type': method.get('teaching-method-name', 'teaching-method'),
                                    'weeks': [],
                                    'lecturers': [],
                                }
                                current.update(tmp)

                            for key in tmp:
                                if current[key] != tmp[key]:

                                    logging.warning('Mismatch %s: %s', self.display(obj), key)
                                    yield current
                                    current = None
                                    break
                            else:
                                current['weeks'].append(e['weeknr'])

                        if current:
                            yield current


def fetch_courses(semester):
    query = {'semester': convert_semester(semester)}
    resp = fetch.plain('https://tp.uio.no/ntnu/timeplan/emner.php', query)
    result = json.loads(re.search(r'var courses = (.+);', resp).group(1))
    return {c['value']: c['name'].split(': ')[1] for c in result}


def fetch_course_lectures(semester, course):
    url = 'https://tp.uio.no/ntnu/ws/1.4/'
    query = {'sem': convert_semester(semester), 'id': course.code.encode('utf-8')}
    result = fetch.json(url, query=query)

    if not result:
        query['termnr'] = 1
        result = fetch.json(url, query=query)

    return result


def convert_semester(semester):
    if semester.type == Semester.FALL:
        return '%sh' % str(semester.year)[-2:]
    else:
        return '%sv' % str(semester.year)[-2:]


def process_groups(values):
    groups = []
    for value in values:
        match = re.match(r'^([A-ZÆØÅ]+)', value, re.U)
        if match:
            groups.append(match.group(1))
    return groups
