# encoding: utf-8

# This file is part of the plan timetable generator, see LICENSE for details.

import logging
import lxml.html
import re
import urllib

from plan.common.models import Course, Semester
from plan.scrape import base
from plan.scrape import fetch
from plan.scrape import ntnu
from plan.scrape import utils

# TODO(adamcik): consider using http://www.ntnu.no/studieinformasjon/rom/?romnr=333A-S041
# selected building will give us the prefix we need to strip to find the actual room
# page will have a link to the building: http://www.ntnu.no/kart/gloeshaugen/berg/
# checking each of the rooms we can find the room name A-S041. Basically we
# should start storing the roomid which we can get in the api, db. for web scraping
# we can get it from http://www.ntnu.no/studieinformasjon/rom for names that
# don't have dupes

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


class Rooms(base.RoomScraper):
    def scrape(self):
        rooms = {}
        for room in self.queryset().filter(code__isnull=False):
            root = fetch.html('http://www.ntnu.no/studieinformasjon/rom/',
                              query={'romnr': room.code}, verbose=True)
            if root is None:
                continue

            for link in root.cssselect('.hovedramme .hoyrebord a'):
                if not link.attrib['href'].startswith('http://www.ntnu.no/kart/'):
                    continue

                root = fetch.html(link.attrib['href'])
                if root is None:
                    continue

                data = {}

                # Sort so that link with the right room name bubbles to the top.
                links = root.cssselect('.facilitylist .horizontallist a')
                links.sort(key=lambda a: (a.text != room.name, a.text))
                for a in links:
                    code, name = fetch_room(a.attrib['href'])
                    if code and room.code.endswith(code):
                        data = {'code': room.code,
                                'name': name,
                                'url': a.attrib['href']}

                    # Give up after first element that should be equal to room
                    # name. Make this conditional on data having been found (i.e.
                    # if data: break) and we will check all rooms to see if we
                    # can find one with a matching code, but this takes a long
                    # time.
                    break

                crumb = root.cssselect('h1.ntnucrumb')
                if crumb[0].text_content() == room.name:
                    links = root.cssselect('link[rel="canonical"]')
                    for link in links:
                        if link.attrib['href'] != 'http://www.ntnu.no/kart/':
                            data = {'code': room.code,
                                    'name': room.name,
                                    'url': link.attrib['href']}

                if data:
                    yield data
                    break


class Lectures(base.LectureScraper):
    def scrape(self):
        url = 'http://www.ntnu.no/web/studier/emner'
        query = {
            'p_p_id': 'coursedetailsportlet_WAR_courselistportlet',
            'p_p_lifecycle': 2,
            'p_p_resource_id': 'timetable',
            '_coursedetailsportlet_WAR_courselistportlet_year': self.semester.year,
        }
        if self.semester.type == Semester.FALL:
            ntnu_semeter = u'%d_HØST' % self.semester.year
        else:
            ntnu_semeter = u'%d_VÅR' % self.semester.year

        for c in self.course_queryset():
            query['_coursedetailsportlet_WAR_courselistportlet_courseCode'] = c.code.encode('utf-8')
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


def fetch_room(url):
    root = fetch.html(url)
    if root is None:
        return None, None

    name = root.cssselect('.ntnukart h2')[0].text_content()
    for div in root.cssselect('.ntnukart .buildingimage .caption'):
        match = re.match(r'[^(]+\(([^)]+)\)', div.text_content())
        if match:
            return match.group(1), name

    return None,None
