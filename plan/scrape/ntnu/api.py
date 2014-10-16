# encoding: utf-8

# This file is part of the plan timetable generator, see LICENSE for details.

import logging
import json

from plan.common.models import Course, Semester
from plan.scrape import base
from plan.scrape import fetch
from plan.scrape import ntnu
from plan.scrape import utils

TERM_MAPPING = {
    Semester.SPRING: 'Spring',
    Semester.FALL: 'Autumn',
}

BASE = 'https://www.ime.ntnu.no/api'


def fetch_courses(semester, prefix=None):
    courses = fetch.json(BASE + '/course/-')['course']
    for course in courses:
        if not ntnu.valid_course_code(course['code']):
            logging.warning('Skipped invalid course name: %s', course['code'])
            continue

        # TODO: shouldn't reimplement should_proccess_course
        if prefix and not course['code'].startswith(prefix):
            continue

        result = fetch_course(course['code'])
        if not result:
             continue

        if semester.year < result['taughtFromYear']:
            continue

        if result['lastYearTaught'] and semester.year > result['lastYearTaught']:
            continue

        if result['versionCode'] != course['versionCode']:
            continue

        if semester.type == semester.FALL and result['taughtInAutumn']:
            yield result
        elif semester.type == semester.SPRING and result['taughtInSpring']:
            yield result


def fetch_course(code):
    code = code.lower().encode('utf-8')
    return fetch.json(BASE + '/course/%s' % code)['course']


def match_term(data, semester):
    return (data['year'] == semester.year and
            data['termApplies'] == TERM_MAPPING[semester.type])


def fetch_buildings():
    data = fetch.json(BASE + '/fdv/buildings')
    return {b['id']: b['nr'] for b in data.get('buildings', [])}


def match_assessment(data, semester):
    return (data['statusCode'] == 'ORD' and
            data['realExecutionYear'] == semester.year and
            data['realExecutionTerm'] == TERM_MAPPING[semester.type])


class Courses(base.CourseScraper):
    def scrape(self):
        for course in fetch_courses(self.semester, self.course_prefix):
            yield {'code': course['code'],
                   'name': course['name'],
                   'version': course['versionCode'],
                   'points': course['credit'],
                   'url': 'http://www.ntnu.no/studier/emner/%s' % course['code']}


class Lectures(base.LectureScraper):
    def scrape(self):
        term = TERM_MAPPING[self.semester.type].lower()
        url = BASE + '/schedule/%%s/%s/%s' % (term, self.semester.year)

        for course in self.course_queryset():
            result = fetch.json(url % course.code.encode('utf-8'))
            if not result:
                continue

            for activity in result['activity'] or []:
                for schedule in activity['activitySchedules']:
                    if 'activityDescription' not in activity:
                        logging.warning('A %s lecture does not have a type', course.code)
                        continue

                    yield {'course': course,
                           'type': activity['activityDescription'],
                           'day':  schedule['dayNumber'],
                           'start': utils.parse_time(schedule['start']),
                           'end':  utils.parse_time(schedule['end']),
                           'weeks': utils.parse_weeks(schedule['weeks'], ','),
                           'rooms': [(r['lydiaCode'], r['location'])
                                     for r in schedule.get('rooms', [])],
                           'lecturers': [s['name'] for s in activity.get('staff', [])],
                           'groups': activity.get('studyProgrammes', [])}


class Exams(base.ExamScraper):
    def scrape(self):
        # Only bother with courses that have already been loaded.
        for course in self.course_queryset():
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
                       'type': self.exam_type(type_code, type_name),
                       'duration': duration}


class Rooms(base.RoomScraper):
    def scrape(self):
        buildings = fetch_buildings()

        qs = self.queryset()
        qs = qs.filter(lecture__course__semester=self.semester)
        qs = qs.distinct()

        for code, name, url in qs.values_list('code', 'name', 'url'):
            if not code or url:
                continue

            data = fetch.json(BASE + '/fdv/rooms/lydiacode:%s' % code)
            if not data:
                continue

            room = data['rooms'][0]
            url = 'http://www.ntnu.no/kart/%s/%s' % (
                 buildings[room['buildingId']], room['nr'])
            name = (room['name'] or '').strip() or 'Rom %s' % room['nr']

            root = fetch.html(url)
            if root:
                for link in root.cssselect('link[rel="canonical"]'):
                    if link.attrib['href'] != 'http://www.ntnu.no/kart':
                        url = link.attrib['href']

            yield {'code': code, 'name': name, 'url': url}
