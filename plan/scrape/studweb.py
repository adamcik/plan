# encoding: utf-8

# This file is part of the plan timetable generator, see LICENSE for details.

import logging
import xml.dom.minidom

from plan.common.models import Exam, ExamType, Course, Semester
from plan.scrape import utils

logger = logging.getLogger('scrape.studweb')


def get_url(semester):
    if Semester.SPRING == semester.type:
        return 'http://www.ntnu.no/eksamen/plan/{0}v/dato.XML'.format(
            str(semester.year)[-2:])
    else:
        return 'http://www.ntnu.no/eksamen/plan/{0}h/dato.XML'.format(
            str(semester.year)[-2:])


def get_element_value(node, tagname):
    child = node.getElementsByTagName(tagname)[0].firstChild
    if child:
        return child.nodeValue
    return None


def update_exams(year, semester, url=None):
    added, updated = [], []
    semester = Semester.objects.get(year=year, type=semester)
    first_day = semester.get_first_day().date()

    if not url:
        url = get_url(semester)

    logger.info('Retrieving %s', url)
    try:
        dom = xml.dom.minidom.parseString(utils.cached_urlopen(url))
    except IOError:
        logger.error('Loading falied')
        return

    for n in dom.getElementsByTagName('dato_row'):
        # Pull out data for this node.
        comment = get_element_value(n, 'kommentar_eksamen')
        course_code = get_element_value(n, 'emnekode')
        course_name = get_element_value(n, 'emne_emnenavn_bokmal')
        course_version = get_element_value(n, 'versjonskode')
        duration = get_element_value(n, 'varighettimer')
        exam_date = get_element_value(n, 'dato_eksamen')
        exam_semester = get_element_value(n, 'terminkode_gjelder_i')
        exam_time = get_element_value(n, 'klokkeslett_fremmote_tid')
        exam_year = get_element_value(n, 'arstall_gjelder_i')
        handin_date = get_element_value(n, 'dato_innlevering')
        handin_time = get_element_value(n, 'klokkeslett_innlevering')
        handout_date = get_element_value(n, 'dato_uttak')
        handout_time = get_element_value(n, 'klokkeslett_uttak')
        long_typename = get_element_value(n, 'vurderingskombinasjon_vurdkombnavn_bokmal')
        status_code = get_element_value(n, 'vurdstatuskode')
        typename = get_element_value(n, 'vurderingsformkode')

        n.unlink()  # Free memory now that we are done with getting data.

        # Sanity check data we've found:
        if not utils.parse_course_code(course_code+'-'+course_version)[0]:
            logger.warning("Bad course code: %s", course_code)
            continue

        if str(year) != exam_year:
            logger.warning("Wrong year for %s: %s", course_code, exam_year)
            continue

        if semester.type == Semester.SPRING and exam_semester != u'VÅR':
            logger.warning("Wrong semester for %s: %s", course_code, exam_semester)
            continue

        if semester.type == Semester.FALL and exam_semester != u'HØST':
            logger.warning("Wrong semester for %s: %s", course_code, exam_semester)
            continue

        # Start building query:
        exam_kwargs = {}

        if exam_date:
            exam_kwargs['exam_date'] = utils.parse_date(exam_date)

        if handin_date:
            exam_kwargs['exam_date'] = utils.parse_date(handin_date)

        if 'exam_date' not in exam_kwargs:
            logger.warning("%s's exam does not have a date.", course_code)
            continue

        if exam_kwargs['exam_date'] < first_day:
            logger.warning("%s's exam is in the past - %s", course_code, exam_kwargs['exam_date'])
            continue

        if status_code != 'ORD':
            continue

        # TODO(adamcik): fail on missing course?
        # TODO(adamcik): use memoized helper to fetch?
        course, created = Course.objects.get_or_create(
                code=course_code.strip(), semester=semester)

        if not course.name and course_name.strip():
            course.name = course_name.strip()
            course.save()

        if not course.version and course_version.strip():
            course.version = course_version.strip()
            course.save()

        exam_kwargs['course'] = course

        if exam_time:
            exam_kwargs['exam_time'] = utils.parse_time(exam_time)

        if handout_date:
            exam_kwargs['handout_date'] = utils.parse_date(handout_date)
        if handout_time:
            exam_kwargs['handout_time'] = utils.parse_time(handout_time)

        if handin_time:
            exam_kwargs['exam_time'] = utils.parse_time(handin_time)

        # Create exam with minimal data for correct lookup:
        try:
            exam, created = Exam.objects.get_or_create(**exam_kwargs)
        except Exam.MultipleObjectsReturned, e:
            print Exam.objects.filter(**exam_kwargs).values()
            raise e

        if created:
            logger.info( "Added exam for %s - %s", course.code, exam.exam_date)
            added.append(exam.id)
        else:
            logger.info("Updated exam for %s - %s", course.code, exam.exam_date)
            updated.append(exam.id)

        # Add additional info that might have changed:
        if duration:
            exam.duration = duration

        if comment:
            exam.comment = comment

        if typename:
            exam_type, created = ExamType.objects.get_or_create(code=typename)

            if long_typename and not exam_type.name:
                exam_type.name = long_typename
                exam_type.save()

            exam.type = exam_type

        exam.save()

    seen_exams = added+updated
    to_delete = list(Exam.objects.filter(course__semester=semester))
    to_delete = filter(lambda e: e.id not in seen_exams, to_delete)

    logger.info('Added %d exams', len(added))
    logger.info('Updated %d exams', len(updated))

    return to_delete
