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
        for course in Course.objects.filter(semester=self.semester):
            result = fetch_course(course.code)
            if not result:
                continue

            for exam in result.get('assessment', []):
                data = {'course': course, 'defaults': {}}

                if not match_assessment(exam, self.semester):
                    continue

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

                if 'duration' in exam and exam['duration']:
                    data['duration'] = exam['duration']

                data['combination'] = exam['combinationCode']
                data['type'] = self.get_exam_type(
                    exam['assessmentFormCode'], exam['assessmentFormDescription'])

                yield data
