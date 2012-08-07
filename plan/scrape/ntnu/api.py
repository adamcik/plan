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


def filter_exams(semester, course):
    year = semester.year
    term = TERM_MAPPING[semester.type]

    for exam in course.get('assessment', []):
        if exam['statusCode'] != 'ORD':
            continue
        if (exam['realExecutionYear'] == year and
            exam['realExecutionTerm'] == term):
            yield exam


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

            # Add all courses that are being taught this semester or have a
            # valid exam this semester.
            if (match_term(self.semester, course) or
                list(filter_exams(self.semester, course))):
                yield {'code': code,
                       'name': course['name'],
                       'version': version,
                       'points': course['credit'],
                       'url': 'http://www.ntnu.no/studier/emner/%s' % code}


class Exams(base.ExamScraper):
    def fetch(self):
        # TODO(adamcik): write a common helper that returns a json for all
        # valid json courses.
        courses = Course.objects.filter(semester=self.semester)
        for course in courses.iterator():
            result = fetch_course(course.code)

            if not result:
                continue

            for exam in filter_exams(self.semester, result):
                data = {'course': course, 'defaults': {}}

                if 'date' in exam:
                    data['exam_date'] = utils.parse_date(exam['date'])
                elif 'submissionDate' in exam:
                    data['exam_date'] = utils.parse_date(exam['submissionDate'])
                else:
                    continue

                if 'appearanceTime' in exam:
                    data['exam_time'] = utils.parse_time(exam['appearanceTime'])

                if 'withdrawalDate' in exam:
                    data['handout_date'] = utils.parse_date(exam['withdrawalDate'])

                if 'duration' in exam and exam['duration'] > 0:
                    data['duration'] = exam['duration']

                data['combination'] = exam['combinationCode']
                data['type'] = self.get_exam_type(
                    exam['assessmentFormCode'], exam['assessmentFormDescription'])

                yield data
