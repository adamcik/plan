# encoding: utf-8

# This file is part of the plan timetable generator, see LICENSE for details.

import logging
import lxml.etree

from plan.common.models import Exam, ExamType, Course, Semester
from plan.scrape import base
from plan.scrape import fetch
from plan.scrape import ntnu
from plan.scrape import utils


def get(row, tagname):
    try:
        return row.xpath('./%s/text()' % tagname).pop()
    except IndexError:
        return None


class Exams(base.ExamScraper):
    def scrape(self):
        prefix = ntnu.prefix(self.semester, template='{year}{letter}')
        url = 'http://www.ntnu.no/eksamen/plan/%s/dato.XML' % prefix

        courses = Course.objects.filter(semester=self.semester)
        courses = dict((c.code, c) for c in courses)

        root = fetch.xml(url)
        if root is None:
            return

        for row in root.xpath('//dato/dato_row'):
            course_code = get(row, 'emnekode')
            course_version = get(row, 'versjonskode')
            status_code = get(row, 'vurdstatuskode')

            if status_code != 'ORD':
                continue
            elif not ntnu.valid_course_code(course_code):
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

            if not type_code:
                logging.warning('Missing exam type for %s', course_code)
                continue

            yield {'course': courses[course_code],
                   'exam_date': utils.parse_date(handin_date or exam_date),
                   'exam_time': utils.parse_time(handin_time or exam_time),
                   'combination': combination,
                   'handout_date': utils.parse_date(handout_date),
                   'handout_time': utils.parse_time(handout_time),
                   'type': self.exam_type(type_code, type_name),
                   'duration': duration}
