# encoding: utf-8

# This file is part of the plan timetable generator, see LICENSE for details.

import logging
import json

from plan.common.models import Semester
from plan.scrape import utils
from plan.scrape import base


class Courses(base.CourseScraper):
    TERM_MAPPING = {
        Semester.SPRING: 'Spring',
        Semester.FALL: 'Autumn',
    }

    def fetch(self):
        data = utils.cached_urlopen('http://www.ime.ntnu.no/api/course/-')

        current_year = self.semester.year
        current_term = self.TERM_MAPPING[self.semester.type]

        for c in json.loads(data)['course']:
            raw_code = '%s-%s' % (c['code'], c['versionCode'])
            code, version = utils.parse_course_code(raw_code)

            if not code:
                logging.warning('Skipped invalid course name: %s', raw_code)
                continue

            url = 'http://www.ime.ntnu.no/api/course/%s' % (
                code.lower().encode('utf-8'))

            try:
                logging.debug('Retrieving %s', url)
                course = json.loads(utils.cached_urlopen(url))['course']
            except IOError as e:
                logging.error('Loading falied: %s', e)
                continue

            for term in course.get('educationTerm', []):
                right_year = term['year'] == current_year
                right_term = term['termApplies'] == current_term

                if not (right_year and right_term):
                    continue

                yield {'code': code,
                       'name': course['name'],
                       'version': version,
                       'points': course['credit'],
                       'url': 'http://www.ntnu.no/studier/emner/%s' % code}
                break
            else:
                # If we make it here the course has no educationTerms or none
                # that match this semester, so indicate that we need remove it.
                yield {'delete': True, 'code': code, 'version': version}
