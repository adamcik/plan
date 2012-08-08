# encoding: utf-8

# This file is part of the plan timetable generator, see LICENSE for details.

import logging
import lxml.html
import re
import urllib

from plan.common.models import Semester
from plan.scrape import base
from plan.scrape import fetch
from plan.scrape import ntnu


# TODO(adamcik): consider using http://www.ntnu.no/web/studier/emner
#   ?p_p_id=courselistportlet_WAR_courselistportlet_INSTANCE_emne
#   &_courselistportlet_WAR_courselistportlet_INSTANCE_emne_year=2011
#   &p_p_lifecycle=2
class Courses(base.CourseScraper):
    def scrape(self):
        prefix = ntnu.prefix(self.semester)
        url = 'http://www.ntnu.no/studieinformasjon/timeplan/%s/' % prefix
        code_re = re.compile('emnekode=([^&]+)', re.I|re.L)

        for letter in u'ABCDEFGHIJKLMNOPQRSTUVWXYZÆØÅ':
            root = fetch.html(url, verbose=True,
                              query={'bokst': letter.encode('latin1')})
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
