# encoding: utf-8

# This file is part of the plan timetable generator, see LICENSE for details.

import logging
import lxml.html
import re
import urllib

from django.db import connections

from plan.common.models import Course, Lecture, Semester
from plan.scrape import utils
from plan.scrape import base


class Courses(base.CourseScraper):
    def get_prefix(self):
        if self.semester.type == Semester.SPRING:
            return 'v%s' % str(self.semester.year)[-2:]
        else:
            return 'h%s' % str(self.semester.year)[-2:]

    def fetch(self):
        prefix = self.get_prefix()
        code_re = re.compile('emnekode=([^&]+)', re.I|re.L)

        for letter in u'ABCDEFGHIJKLMNOPQRSTUVWXYZÆØÅ':
            url = 'http://www.ntnu.no/studieinformasjon/timeplan/{0}/?{1}'.format(
                prefix, urllib.urlencode({'bokst': letter.encode('latin1')}))

            try:
                logging.info('Retrieving %s', url)
                root = lxml.html.fromstring(utils.cached_urlopen(url))
            except IOError as e:
                logging.error('Loading falied: %s', e)
                continue

            for tr in root.cssselect('.hovedramme table table tr'):
                code_link, name_link = tr.cssselect('a')

                code_href = code_link.attrib['href']
                raw_code = code_re.search(code_href).group(1)

                code, version = utils.parse_course_code(raw_code)
                if not code:
                    logging.warning('Skipped invalid course name: %s', code)
                    continue

                # Strip out noise in course name.
                name = re.search(r'(.*)(\(Nytt\))?', name_link.text_content()).group(1)

                yield {'code': code,
                       'name': name.strip(),
                       'version': version,
                       'url': 'http://www.ntnu.no/studier/emner/%s' % code}
