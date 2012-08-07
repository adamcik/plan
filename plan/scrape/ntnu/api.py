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


def fetch_courses(semester):
    data = utils.cached_urlopen('http://www.ime.ntnu.no/api/course/-')
    for course in json.loads(data)['course']:
        # TODO(adamcik): need utils that does not require version.
        raw_code = '%s-%s' % (course['code'], course['versionCode'])
        if not utils.parse_course_code(raw_code)[0]:
            logging.warning('Skipped invalid course name: %s', raw_code)
            continue

        result = fetch_course(course['code'])
        if not result:
            continue

        match = False
        for term in result.get('educationTerm', []):
            match |= match_term(term, semester)
        for assessment in result.get('assessment', []):
            match |= match_assessment(assessment, semester)

        if match:
            yield result


# TODO(adamcik): replace with fetch_json fetch_xml fetch_html etc?
def fetch_course(code):
    code = code.lower().encode('utf-8')
    url = 'http://www.ime.ntnu.no/api/course/%s' % code

    try:
        logging.debug('Retrieving %s', url)
        return json.loads(utils.cached_urlopen(url))['course']
    except IOError as e:
        logging.error('Loading falied: %s', e)


def match_term(data, semester):
    return (data['year'] == semester.year and
            data['termApplies'] == TERM_MAPPING[semester.type])


def match_assessment(data, semester):
    return (data['statusCode'] == 'ORD' and
            data['realExecutionYear'] == semester.year and
            data['realExecutionTerm'] == TERM_MAPPING[semester.type])


class Courses(base.CourseScraper):
    def fetch(self):
        for course in fetch_courses(self.semester):
            yield {'code': course['code'],
                   'name': course['name'],
                   'version': course['versionCode'],
                   'points': course['credit'],
                   'url': 'http://www.ntnu.no/studier/emner/%s' % course['code']}


class Exams(base.ExamScraper):
    def fetch(self):
        # Only bother with courses that have already been loaded.
        for course in Course.objects.filter(semester=self.semester):
            result = fetch_course(course.code)
            if not result:
                continue

            for exam in result.get('assessment', []):
                if not match_assessment(exam, self.semester):
                    continue

                exam_date = exam.get('date', None)
                exam_time = exam.get('appearanceTime', None)
                handout_date = exam.get('withdrawalDate', None)
                handin_date = exam.get('submissionDate', None)
                duration = exam.get('duration', None)
                combination = exam['combinationCode']
                type_code = exam['assessmentFormCode']
                type_name = exam['assessmentFormDescription']

                yield {'course': course,
                       'exam_date': utils.parse_date(handin_date or exam_date),
                       'exam_time': utils.parse_time(exam_time),
                       'combination': combination,
                       'handout_date': utils.parse_date(handout_date),
                       'type': self.get_exam_type(type_code, type_name),
                       'duration': duration}
