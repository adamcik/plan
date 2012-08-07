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
            combination = get(row, 'vurdkombkode')
            course_code = get(row, 'emnekode')
            course_name = get(row, 'emne_emnenavn_bokmal')
            course_version = get(row, 'versjonskode')
            duration = get(row, 'varighettimer')
            exam_date = get(row, 'dato_eksamen')
            exam_semester = get(row, 'terminkode_gjelder_i')
            exam_time = get(row, 'klokkeslett_fremmote_tid')
            exam_year = get(row, 'arstall_gjelder_i')
            handin_date = get(row, 'dato_innlevering')
            handin_time = get(row, 'klokkeslett_innlevering')
            handout_date = get(row, 'dato_uttak')
            handout_time = get(row, 'klokkeslett_uttak')
            long_typename = get(row, 'vurderingskombinasjon_vurdkombnavn_bokmal')
            status_code = get(row, 'vurdstatuskode')
            typename = get(row, 'vurderingsformkode')

            if status_code != 'ORD':
                continue

            if not utils.parse_course_code(course_code+'-'+course_version)[0]:
                logging.warning("Bad course code: %s", course_code)
                continue
            elif course_code not in courses:
                logging.warning("Unknown course %s for this semester.", course_code)
                continue

            data = {'course': courses[course_code]}
            data['exam_date'] = utils.parse_date(handin_date or exam_date)
            data['exam_time'] = utils.parse_time(handin_time or exam_time)
            data['combination'] = combination

            data['handout_date'] = utils.parse_date(handout_date)
            data['handout_time'] = utils.parse_time(handout_time)
            data['type'] = self.get_exam_type(typename, long_typename)

            if duration:
                data['duration'] = duration

            yield data
