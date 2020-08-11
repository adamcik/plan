# encoding: utf-8

# This file is part of the plan timetable generator, see LICENSE for details.

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
                'locations': course['location'].split(','),
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
        if self.semester.type == Semester.FALL:
            ntnu_semeter = u'%d_HØST' % self.semester.year
        else:
            ntnu_semeter = u'%d_VÅR' % self.semester.year

        for c in self.course_queryset():
            course = fetch_course_lectures(self.semester, c)
            for activity in course.get('summarized', []):
                if activity['artermin'] != ntnu_semeter:
                    continue

                groups = activity.get('studyProgramKeys', [])
                title = re.sub(r'^\d+(-\d*)?\s?', '', activity['title']).strip(' ')

                if not title or title == c.code:
                    title = None

                if not groups and title:
                    groups = [title]
                    title = None

                if activity['name'] in ('Seminar', 'Gruppe') and title != activity['name']:
                    groups.append(title)
                    title = None

                yield {
                    'course': c,
                    'type': activity.get('name', activity['acronym']),
                    'day': activity['dayNum'] - 1,
                    'start': utils.parse_time(activity['from']),
                    'end':  utils.parse_time(activity['to']),
                    'weeks': utils.parse_weeks(','.join(activity['weeks']), ','),
                    'rooms': [(r['id'], r['room'], r.get('url'))
                               for r in activity.get('rooms', [])],
                    'groups': groups,
                    'lecturers': [],
                    'title': title,
                }


class Rooms(base.RoomScraper):
    def scrape(self):
        seen = set()
        for c in Course.objects.filter(semester=self.semester):
            course = fetch_course_lectures(self.semester, c)
            for activity in course.get('summarized', []):
                for room in activity.get('rooms', []):
                    if room['syllabusKey'] not in seen:
                        seen.add(room['syllabusKey'])
                        yield {'code': room['syllabusKey'],
                               'name': room['romNavn'],
                               'url': room.get('url')}


def fetch_course_lectures(semester, course):
    url = 'https://www.ntnu.no/web/studier/emner'
    query = {
        'p_p_id': 'coursedetailsportlet_WAR_courselistportlet',
        'p_p_lifecycle': 2,
        'p_p_resource_id': 'timetable',
        '_coursedetailsportlet_WAR_courselistportlet_year': semester.year,
        '_coursedetailsportlet_WAR_courselistportlet_courseCode': course.code.encode('utf-8'),
        'year': semester.year,
        'version': course.version,
    }
    return fetch.json(url, query=query, data={})


def fetch_courses(semester):
    """
    https://www.ntnu.no/web/studier/emnesok?
        p_p_id=courselistportlet_WAR_courselistportlet
        p_p_lifecycle=2
        p_p_state=normal
        p_p_mode=view
        p_p_resource_id=fetch-courselist-as-json
        p_p_cacheability=cacheLevelPage
        p_p_col_id=column-1
        p_p_col_pos=1
        p_p_col_count=2

    X-Requested-With: XMLHttpRequest
    Cookie: GUEST_LANGUAGE_ID=nb_NO

    Data:
        semester=2018
        gjovik=0
        trondheim=1
        alesund=0
        faculty=-1
        institute=-1
        multimedia=0
        english=0
        phd=0
        courseAutumn=0
        courseSpring=1
        courseSummer=0
        searchQueryString=
        pageNo=1
        season=spring
        sortOrder=%2Btitle
        year=
    """

    if semester.type == Semester.FALL:
        year = semester.year
    else:
        year = semester.year - 1

    url = 'https://www.ntnu.no/web/studier/emnesok'

    query = {
        'p_p_id': 'courselistportlet_WAR_courselistportlet',
        'p_p_lifecycle': '2',
        'p_p_mode': 'view',
        'p_p_resource_id': 'fetch-courselist-as-json'
    }

    data = {
        'english': 0,
        'pageNo': 1,
        'semester': year,
        'sortOrder': '+title',
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
