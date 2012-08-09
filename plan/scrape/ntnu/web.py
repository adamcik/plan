# encoding: utf-8

# This file is part of the plan timetable generator, see LICENSE for details.

import logging
import lxml.html
import re
import urllib

from plan.common.models import Course
from plan.scrape import base
from plan.scrape import fetch
from plan.scrape import ntnu
from plan.scrape import utils

LETTERS = u'ABCDEFGHIJKLMNOPQRSTUVWXYZÆØÅ'


# TODO(adamcik): consider using http://www.ntnu.no/web/studier/emner
#   ?p_p_id=courselistportlet_WAR_courselistportlet_INSTANCE_emne
#   &_courselistportlet_WAR_courselistportlet_INSTANCE_emne_year=2011
#   &p_p_lifecycle=2

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
        prefix = ntnu.prefix(self.semester)
        url = 'http://www.ntnu.no/studieinformasjon/timeplan/%s/' % prefix
        code_re = re.compile('emnekode=([^&]+)', re.I|re.L)

        for letter in LETTERS:
            root = fetch.html(
                url, verbose=True, query={'bokst': letter.encode('latin1')})
            if root is None:
                continue

            for tr in root.cssselect('.hovedramme table table tr'):
                code_link, name_link = tr.cssselect('a')

                code_href = code_link.attrib['href']
                raw_code = code_re.search(code_href).group(1)

                code, version = ntnu.parse_course(raw_code)
                if not code:
                    logging.warning('Skipped invalid course name: %s', raw_code)
                    continue

                # Strip out noise in course name.
                name = re.search(r'(.*)(\(Nytt\))?', name_link.text_content()).group(1)

                yield {'code': code,
                       'name': name.strip(),
                       'version': version,
                       'url': 'http://www.ntnu.no/studier/emner/%s' % code}

    def prepare_delete(self, qs, pks):
        return qs.none()

    def log_finished(self):
        super(Courses, self).log_finished()
        logging.warning('This scraper only knows about courses on timetable')
        logging.warning('website, not deleting any unknown courses.')


class Lectures(base.LectureScraper):
    def scrape(self):
        prefix = ntnu.prefix(self.semester)
        url = 'http://www.ntnu.no/studieinformasjon/timeplan/%s/' % prefix

        for course in Course.objects.filter(semester=self.semester).order_by('code'):
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
                data = {}

                for i, td in enumerate(tr.cssselect('td')):
                    if i == 0:
                        if td.attrib.get('colspan', 1) == '4':
                            lecture_type = td.text_content().strip()
                        else:
                            time = td.cssselect('b')[0].text_content().strip()
                            raw_day, period = time.split(' ', 1)
                            raw_start, raw_end = period.split('-')

                            data['day'] = utils.parse_day_of_week(raw_day)
                            data['start'] = utils.parse_time(raw_start)
                            data['end'] = utils.parse_time(raw_end)

                            match = re.match('.*Uke: (.+)', td.text_content())
                            data['weeks'] = utils.parse_weeks(match.group(1))
                    elif i == 1 and len(td.cssselect('a')) == 1:
                        a = td.cssselect('a')[0]
                        data['rooms'] = [a.text] + [e.tail for e in a]
                    elif i == 2:
                        data['lecturers'] = [td.text] + [e.tail for e in td]
                    elif i == 3:
                        data['groups'] = [g.text_content() for g in td.cssselect('span')]

                for field in ('rooms', 'lecturers', 'groups'):
                    if field in data:
                        data[field] = utils.clean_list(data[field], utils.clean_string)

                if data:
                    data.update({'course': course, 'type': lecture_type})
                    yield data
