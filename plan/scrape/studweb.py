# encoding: utf-8

# Copyright 2008, 2009 Thomas Kongevold Adamcik
# 2009 IME Faculty Norwegian University of Science and Technology

# This file is part of Plan.
#
# Plan is free software: you can redistribute it and/or modify
# it under the terms of the Affero GNU General Public License as
# published by the Free Software Foundation, either version 3 of
# the License, or (at your option) any later version.
#
# Plan is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# Affero GNU General Public License for more details.
#
# You should have received a copy of the Affero GNU General Public
# License along with Plan.  If not, see <http://www.gnu.org/licenses/>.

import logging
from urllib2 import urlopen, HTTPError
from xml.dom import minidom
from dateutil.parser import parse

from plan.common.models import Exam, ExamType, Course, Semester

logger = logging.getLogger('scrape.studweb')

def _url(semester):
    if Semester.SPRING == semester.type:
        return 'http://www.ntnu.no/eksamen/plan/%sv/dato.XML' \
            % str(semester.year)[-2:]
    else:
        return 'http://www.ntnu.no/eksamen/plan/%sh/dato.XML' \
            % str(semester.year)[-2:]

def update_exams(year, semester, url=None):
    added, updated = [], []
    semester = Semester.objects.get(year=year, type=semester)
    first_day = semester.get_first_day().date()

    if not url:
        url = _url(semester)

    logger.info('Getting url: %s', url)

    try:
        xml_data = urlopen(url).read()
    except HTTPError, e:
        logger.error('XML retrival failed: %s', e)
        return

    dom = minidom.parseString(xml_data)


    for n in dom.getElementsByTagName('dato_row'):
        course_code = n.getElementsByTagName('emnekode')[0].firstChild
        course_name = n.getElementsByTagName('emne_emnenavn_bokmal')[0].firstChild
        course_version = n.getElementsByTagName('versjonskode')[0].firstChild

        exam_year = n.getElementsByTagName('arstall_gjelder_i')[0].firstChild

        if str(year) != exam_year.nodeValue:
            logger.warning("Wrong year for %s: %s" % (course_code.nodeValue, exam_year.nodeValue))
            n.unlink()
            continue

        exam_semester = n.getElementsByTagName('terminkode_gjelder_i')[0].firstChild

        if semester.type == Semester.SPRING and exam_semester.nodeValue != u'VÅR':
            logger.warning("Wrong semester for %s: %s" % (course_code.nodeValue, exam_semester.nodeValue))
            n.unlink()
            continue

        if semester.type == Semester.FALL and exam_semester.nodeValue != u'HØST':
            logger.warning("Wrong semester for %s: %s" % (course_code.nodeValue, exam_semester.nodeValue))
            n.unlink()
            continue

        exam_kwargs = {}

        exam_date = n.getElementsByTagName('dato_eksamen')[0].firstChild
        if exam_date:
            exam_kwargs['exam_date'] = parse(exam_date.nodeValue).date()

        handin_date = n.getElementsByTagName('dato_innlevering')[0].firstChild
        if handin_date:
            exam_kwargs['exam_date'] = parse(handin_date.nodeValue).date()

        if 'exam_date' not in exam_kwargs:
            logger.warning("%s's exam does not have a date." % (course_code.nodeValue))
            n.unlink()
            continue

        if exam_kwargs['exam_date'] < first_day:
            logger.warning("%s's exam is in the past - %s" % (course_code.nodeValue, exam_kwargs['exam_date']))
            n.unlink()
            continue

        exam_time = n.getElementsByTagName('klokkeslett_fremmote_tid') \
                [0].firstChild

        handout_date = n.getElementsByTagName('dato_uttak')[0].firstChild
        handout_time = n.getElementsByTagName('klokkeslett_uttak') \
                [0].firstChild

        handin_time = n.getElementsByTagName('klokkeslett_innlevering') \
                [0].firstChild

        duration = n.getElementsByTagName('varighettimer')[0].firstChild

        long_typename_key = 'vurderingskombinasjon_vurdkombnavn_bokmal'
        long_typename = n.getElementsByTagName(long_typename_key) \
                [0].firstChild
        typename = n.getElementsByTagName('vurderingsformkode') \
                [0].firstChild

        status_code = n.getElementsByTagName('vurdstatuskode') \
                [0].firstChild

        comment = n.getElementsByTagName('kommentar_eksamen') \
                [0].firstChild

        if not status_code or status_code.nodeValue != 'ORD':
            n.unlink()
            continue

        if not course_code.nodeValue.strip():
            continue

        course, created = Course.objects.get_or_create(
                code=course_code.nodeValue.strip(), semester=semester)

        if not course.name and course_name.nodeValue.strip():
            course.name = course_name.nodeValue.strip()
            course.save()

        if not course.version and course_version.nodeValue.strip():
            course.version = course_version.nodeValue.strip()
            course.save()

        exam_kwargs['course'] = course

        if exam_time:
            exam_kwargs['exam_time'] = parse(exam_time.nodeValue).time()

        if handout_date:
            exam_kwargs['handout_date'] = parse(handout_date.nodeValue) \
                    .date()
        if handout_time:
            exam_kwargs['handout_time'] = parse(handout_time.nodeValue) \
                    .time()

        if handin_time:
            exam_kwargs['exam_time'] = parse(handin_time.nodeValue).time()

        try:
            exam, created = Exam.objects.get_or_create(**exam_kwargs)
        except Exam.MultipleObjectsReturned, e:
            print Exam.objects.filter(**exam_kwargs).values()
            raise e

        if created:
            logger.info( "Added exam for %s - %s" % (course.code, exam.exam_date))
            added.append(exam.id)
        else:
            logger.debug("Updated exam for %s - %s" %( course.code, exam.exam_date))
            updated.append(exam.id)

        if duration:
            exam.duration = duration.nodeValue

        if comment:
            exam.comment = comment.nodeValue


        if typename:
            exam_type, created = ExamType.objects.get_or_create(code=typename.nodeValue)

            if long_typename and not exam_type.name:
                exam_type.name = long_typename.nodeValue
                exam_type.save()

            exam.type = exam_type

        exam.save()

        n.unlink()

    seen_exams = added+updated
    to_delete = list(Exam.objects.filter(course__semester=semester))
    to_delete = filter(lambda e: e.id not in seen_exams, to_delete)

    logger.info('Added %d exams' % len(added))
    logger.info('Updated %d exams' % len(updated))

    return to_delete
