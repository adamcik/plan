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
        if self.semester.type == Semester.FALL:
            year = self.semester.year
        else:
            year = self.semester.year - 1

        code_re = re.compile('/studier/emner/([^/]+)/', re.I|re.L)

        url = 'http://www.ntnu.no/web/studier/emnesok'
        query = {
            'p_p_lifecycle': '2',
            'p_p_id': 'courselistportlet_WAR_courselistportlet_INSTANCE_m8nT',
            '_courselistportlet_WAR_courselistportlet_INSTANCE_m8nT_year': year}

        courses_root = fetch.html(url, query=query, verbose=True)
        for a in courses_root.cssselect('a[href*="/studier/emner/"]'):
            course_url = a.attrib['href']
            code = code_re.search(course_url).group(1)
            quoted_code = urllib.quote(code.encode('utf-8'))
            name = a.text_content()

            if not ntnu.valid_course_code(code):
                continue
            elif not self.should_proccess_course(code):
                continue

            title = None
            data = {}
            root = fetch.html(
                'http://www.ntnu.no/studier/emner/%s/%s' % (quoted_code, year))

            # Construct dict out of info boxes.
            for box in root.cssselect('.infoBox'):
                for child in box.getchildren():
                    if child.tag == 'h3':
                        title = child.text_content()
                    else:
                        parts = [child.text or '']
                        for br in child.getchildren():
                            parts.append(br.tail or '')
                        for key, value in [p.split(':', 1) for p in parts if ':' in p]:
                            key = key.strip(u' \n\xa0')
                            value = value.strip(u' \n\xa0')
                            data.setdefault(title, {}).setdefault(key, []).append(value)

            try:
                semesters = data['Undervisning']['Undervises']
            except KeyError:
                continue

            if self.semester.type == Semester.FALL and u'HØST %s' % year not in semesters:
                continue
            elif self.semester.type == Semester.SPRING and u'VÅR %s' % year not in semesters:
                continue

            yield {'code': code,
                   'name': name,
                   'version': int(data['Fakta om emnet']['Versjon'][0]),
                   'points': float(data['Fakta om emnet']['Studiepoeng'][0]),
                   'url': course_url}


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
                for a in sorted(root.cssselect('.facilitylist .horizontallist a'),
                                key=lambda a: (a.text != room.name, a.text)):
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

                if data:
                    yield data
                    break


class Lectures(base.LectureScraper):
    def scrape(self):
        prefix = ntnu.prefix(self.semester)
        url = 'http://www.ntnu.no/studieinformasjon/timeplan/%s/' % prefix
        room_codes = {}

        for code, name in fetch_rooms():
            room_codes.setdefault(name, []).append(code)

        for course in self.course_queryset():
            code = '%s-%s' % (course.code, course.version)
            root = fetch.html(url, query={'emnekode': code.encode('latin1')})
            if root is None:
                continue

            for h1 in root.cssselect(u'.hovedramme h1'):
                if course.code in h1.text_content():
                    table = root.cssselect('.hovedramme table')[1];
                    break
            else:
                logging.debug("Couldn't load any info for %s", course.code)
                continue

            lecture_type = None
            for tr in table.cssselect('tr')[1:-1]:
                data = parse_row(tr, room_codes)
                if data.get('lecture_type', None):
                    lecture_type = data['lecture_type']
                elif data:
                    data.update({'course': course, 'type': lecture_type})
                    yield data


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


def fetch_rooms():
    result = fetch.html('http://www.ntnu.no/studieinformasjon/rom/')
    if result is None:
        return

    rooms = {}
    for option in result.cssselect('.hovedramme select[name="romnr"] option'):
        code = utils.clean_string(option.attrib['value'])
        name = utils.clean_string(option.text_content())

        if code and name and 'ikkerom' not in name:
            yield code, name


def parse_row(tr, room_codes):
    data = {}
    for i, td in enumerate(tr.cssselect('td')):
        if i == 0:
            if td.attrib.get('colspan', 1) == '4':
                lecture_type = utils.clean_string(td.text_content())
                if lecture_type:
                    data['lecture_type'] = lecture_type
            else:
                time = td.cssselect('b')[0].text_content().strip()
                raw_day, period = time.split(' ', 1)
                raw_start, raw_end = period.split('-')

                data['day'] = utils.parse_day_of_week(raw_day)
                data['start'] = utils.parse_time(raw_start)
                data['end'] = utils.parse_time(raw_end)

                match = re.match('.*Uke: (.+)', td.text_content())
                data['weeks'] = utils.parse_weeks(match.group(1))
        elif i == 1 and len(td.cssselect('a')) > 0:
            if len(td.cssselect('a')) > 1:
                logging.warning('Multiple rooms links found, simply '
                                'using first one.')

            a = td.cssselect('a')[0]
            rooms = [a.text] + [e.tail for e in a]

            data['rooms'] = []
            for name in utils.clean_list(rooms, utils.clean_string):
                if name not in room_codes:
                    data['rooms'].append((None, name))
                    continue

                if len(room_codes[name]) > 1:
                    logging.warning('Multiple rooms with name %s, '
                                    'simply using first code.', name)
                data['rooms'].append((room_codes[name][0], name))
        elif i == 2:
            data['lecturers'] = [td.text] + [e.tail for e in td]
        elif i == 3:
            data['groups'] = [g.text_content() for g in td.cssselect('span')]

    return data
