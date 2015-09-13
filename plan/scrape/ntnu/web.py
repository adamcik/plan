# encoding: utf-8

# This file is part of the plan timetable generator, see LICENSE for details.

import logging
import lxml.html
import re
import urllib

from plan.common.models import Course, ExamType, Semester
from plan.scrape import base
from plan.scrape import fetch
from plan.scrape import ntnu
from plan.scrape import utils

# TODO(adamcik): link to http://www.ntnu.no/eksamen/sted/?dag=120809 for exams?

class Courses(base.CourseScraper):
    def scrape(self):
        for course in fetch_courses(self.semester):
            yield {
                'code': course['courseCode'],
                'name': course['courseName'],
                'version': course['courseVersion'],
                'url': course['courseUrl'],
            }


class Exams(base.ExamScraper):
    def scrape(self):
        for course in fetch_courses(self.semester):
            seen = set()
            for exam in course['exam']:
                if not exam.get('date'):
                    continue
                elif self.semester.type == Semester.FALL and exam['season'] != 'AUTUMN':
                    continue
                elif self.semester.type == Semester.SPRING and exam['season'] != 'SPRING':
                    continue

                date = utils.parse_date(exam['date'])
                if date in seen:
                    continue

                seen.add(date)
                yield {
                    'course': Course.objects.get(
                        code=course['courseCode'],
                        version=course['courseVersion'],
                        semester=self.semester),
                    'exam_date': date,
                }


class Lectures(base.LectureScraper):
    def scrape(self):
        url = 'http://www.ntnu.no/web/studier/emner'
        query = {
            'p_p_id': 'coursedetailsportlet_WAR_courselistportlet',
            'p_p_lifecycle': 2,
            'p_p_resource_id': 'timetable',
            '_coursedetailsportlet_WAR_courselistportlet_year': self.semester.year,
            'year': self.semester.year,
        }
        if self.semester.type == Semester.FALL:
            ntnu_semeter = u'%d_HØST' % self.semester.year
        else:
            ntnu_semeter = u'%d_VÅR' % self.semester.year

        for c in self.course_queryset():
            query['_coursedetailsportlet_WAR_courselistportlet_courseCode'] = c.code.encode('utf-8')
            query['version'] = c.version
            course = fetch.json(url, query=query, data={})['course']
            for activity in course.get('summarized', []):
                if activity['arsterminId'] != ntnu_semeter:
                    continue
                yield {
                    'course': c,
                    'type': activity.get('description', activity['acronym']),
                    'day': activity['dayNum'] - 1,
                    'start': utils.parse_time(activity['from']),
                    'end':  utils.parse_time(activity['to']),
                    'weeks': utils.parse_weeks(','.join(activity['weeks']), ','),
                    'rooms': [(r['syllabusKey'], r['romNavn'])
                               for r in activity.get('rooms', [])],
                    'groups': activity.get('studyProgramKeys', []),
                    'lecturers': [],
                }


def fetch_courses(semester):
    if semester.type == Semester.FALL:
        year = semester.year
    else:
        year = semester.year - 1

    url = 'http://www.ntnu.no/web/studier/emnesok'
    query = {
        'p_p_lifecycle': '2',
        'p_p_id': 'courselistportlet_WAR_courselistportlet',
        'p_p_mode': 'view',
        'p_p_resource_id': 'fetch-courselist-as-json'
    }
    data = {
        'english': 0,
        'pageNo': 1,
        'semester': year,
        'sortOrder': '+title'
    }
    if semester.type == Semester.FALL:
        data['courseAutumn'] = 1
    else:
        data['courseSpring'] = 1


    while True:
        result = fetch.json(url, query=query, data=data, verbose=True)
        data['pageNo'] += 1

        if not result['courses']:
            break

        for course in result['courses']:
            yield course
