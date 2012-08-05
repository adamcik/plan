# encoding: utf-8

# This file is part of the plan timetable generator, see LICENSE for details.

import logging
import json

from plan.common.models import Course, Semester
from plan.scrape import utils
from plan.scrape import base

TERM_MAPPING = {
    Semester.SPRING: 'Spring',
    Semester.FALL: 'Autumn',
}


def fetch_course(code):
    url = 'http://www.ime.ntnu.no/api/course/%s' % (
        code.lower().encode('utf-8'))

    try:
        logging.debug('Retrieving %s', url)
        return json.loads(utils.cached_urlopen(url))['course']
    except IOError as e:
        logging.error('Loading falied: %s', e)
        return None


def match_term(semester, course):
    year = semester.year
    term = TERM_MAPPING[semester.type]

    for t in course.get('educationTerm', []):
        if t['year'] == year and t['termApplies'] == term:
            return True
    return False


class Courses(base.CourseScraper):
    def fetch(self):
        data = utils.cached_urlopen('http://www.ime.ntnu.no/api/course/-')

        for c in json.loads(data)['course']:
            raw_code = '%s-%s' % (c['code'], c['versionCode'])
            code, version = utils.parse_course_code(raw_code)

            if not code:
                logging.warning('Skipped invalid course name: %s', raw_code)
                continue

            course = fetch_course(code)
            if not course:
                continue

            if match_term(self.semester, course):
                yield {'code': code,
                       'name': course['name'],
                       'version': version,
                       'points': course['credit'],
                       'url': 'http://www.ntnu.no/studier/emner/%s' % code}
            else:
                yield {'delete': True, 'code': code, 'version': version}
