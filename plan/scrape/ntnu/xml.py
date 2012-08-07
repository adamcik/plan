# encoding: utf-8

# This file is part of the plan timetable generator, see LICENSE for details.

import logging
import lxml.etree

from plan.common.models import Exam, ExamType, Course, Semester
from plan.scrape import base
from plan.scrape import utils


def get(row, tagname):
    try:
        return row.xpath('./%s/text()' % tagname).pop()
    except IndexError:
        return None


class Exams(base.ExamScraper):
    def get_prefix(self):
        if Semester.SPRING == self.semester.type:
            return '%sv' % str(self.semester.year)[-2:]
        return '%sh' % str(self.semester.year)[-2:]

    def get_value(self, node, tagname):
        child = node.getElementsByTagName(tagname)[0].firstChild
        if child:
            return child.nodeValue
        return None

    def fetch(self):
        url = 'http://www.ntnu.no/eksamen/plan/%s/dato.XML' % self.get_prefix()

        courses = Course.objects.filter(semester=self.semester)
        courses = dict((c.code, c) for c in courses)

        try:
            root = lxml.etree.fromstring(utils.cached_urlopen(url))
        except IOError:
            logging.error('Loading falied')
            return

        for row in root.xpath('//dato/dato_row'):
            course_code = get(row, 'emnekode')
            course_version = get(row, 'versjonskode')
            status_code = get(row, 'vurdstatuskode')

            if status_code != 'ORD':
                continue
            elif not utils.parse_course_code(course_code+'-'+course_version)[0]:
                logging.warning("Invalid course code: %s", course_code)
                continue
            elif course_code not in courses:
                logging.debug("Unknown course %s.", course_code)
                continue

            combination = get(row, 'vurdkombkode')
            duration = get(row, 'varighettimer')
            exam_date = get(row, 'dato_eksamen')
            exam_semester = get(row, 'terminkode_gjelder_i')
            exam_time = get(row, 'klokkeslett_fremmote_tid')
            exam_year = get(row, 'arstall_gjelder_i')
            handin_date = get(row, 'dato_innlevering')
            handin_time = get(row, 'klokkeslett_innlevering')
            handout_date = get(row, 'dato_uttak')
            handout_time = get(row, 'klokkeslett_uttak')
            type_code = get(row, 'vurderingsformkode')
            type_name = get(row, 'vurderingskombinasjon_vurdkombnavn_bokmal')

            yield {'course': courses[course_code],
                   'exam_date': utils.parse_date(handin_date or exam_date),
                   'exam_time': utils.parse_time(handin_time or exam_time),
                   'combination': combination,
                   'handout_date': utils.parse_date(handout_date),
                   'handout_time': utils.parse_time(handout_time),
                   'type': self.get_exam_type(type_code, type_name),
                   'duration': duration}
