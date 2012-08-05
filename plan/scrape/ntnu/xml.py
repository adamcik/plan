# encoding: utf-8

# This file is part of the plan timetable generator, see LICENSE for details.

import logging

import xml.dom.minidom

from plan.common.models import Exam, ExamType, Course, Semester
from plan.scrape import base
from plan.scrape import utils

class Exams(base.Scraper):
    def get_url(self):
        if Semester.SPRING == self.semester.type:
            return 'http://www.ntnu.no/eksamen/plan/{0}v/dato.XML'.format(
                str(self.semester.year)[-2:])
        else:
            return 'http://www.ntnu.no/eksamen/plan/{0}h/dato.XML'.format(
                str(self.semester.year)[-2:])

    def get_value(self, node, tagname):
        child = node.getElementsByTagName(tagname)[0].firstChild
        if child:
            return child.nodeValue
        return None

    # TODO(adamcik): use memoization?
    def get_semester(self):
        return Semester.objects.get(year=self.semester.year,
                                    type=self.semester.type)

    # TODO(adamcik): fail on missing course?
    # TODO(adamcik): use memoization?
    def get_course(self, code):
        course, created = Course.objects.get_or_create(
            code=code.strip(), semester=self.get_semester())
        return course

    def run(self):
        added, updated = [], []
        semester = self.get_semester()
        first_day = semester.get_first_day().date()

        url = self.get_url()
        try:
            logging.info('Retrieving %s', url)
            dom = xml.dom.minidom.parseString(utils.cached_urlopen(url))
        except IOError:
            logging.error('Loading falied')
            return

        for n in dom.getElementsByTagName('dato_row'):
            # Pull out data for this node.
            comment = self.get_value(n, 'kommentar_eksamen')
            course_code = self.get_value(n, 'emnekode')
            course_name = self.get_value(n, 'emne_emnenavn_bokmal')
            course_version = self.get_value(n, 'versjonskode')
            duration = self.get_value(n, 'varighettimer')
            exam_date = self.get_value(n, 'dato_eksamen')
            exam_semester = self.get_value(n, 'terminkode_gjelder_i')
            exam_time = self.get_value(n, 'klokkeslett_fremmote_tid')
            exam_year = self.get_value(n, 'arstall_gjelder_i')
            handin_date = self.get_value(n, 'dato_innlevering')
            handin_time = self.get_value(n, 'klokkeslett_innlevering')
            handout_date = self.get_value(n, 'dato_uttak')
            handout_time = self.get_value(n, 'klokkeslett_uttak')
            long_typename = self.get_value(n, 'vurderingskombinasjon_vurdkombnavn_bokmal')
            status_code = self.get_value(n, 'vurdstatuskode')
            typename = self.get_value(n, 'vurderingsformkode')

            n.unlink()  # Free memory now that we are done with getting data.

            # Sanity check data we've found:
            if not utils.parse_course_code(course_code+'-'+course_version)[0]:
                logging.warning("Bad course code: %s", course_code)
                continue

            if str(semester.year) != exam_year:
                logging.warning("Wrong year for %s: %s", course_code, exam_year)
                continue

            if semester.type == Semester.SPRING and exam_semester != u'VÅR':
                logging.warning("Wrong semester for %s: %s", course_code, exam_semester)
                continue

            if semester.type == Semester.FALL and exam_semester != u'HØST':
                logging.warning("Wrong semester for %s: %s", course_code, exam_semester)
                continue

            # Start building query:
            exam_kwargs = {}

            if exam_date:
                exam_kwargs['exam_date'] = utils.parse_date(exam_date)

            if handin_date:
                exam_kwargs['exam_date'] = utils.parse_date(handin_date)

            if 'exam_date' not in exam_kwargs:
                logging.warning("%s's exam does not have a date.", course_code)
                continue

            if exam_kwargs['exam_date'] < first_day:
                logging.warning("%s's exam is in the past - %s", course_code, exam_kwargs['exam_date'])
                continue

            if status_code != 'ORD':
                continue

            course = self.get_course(course_code)

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
                logging.info( "Added exam for %s - %s", course.code, exam.exam_date)
                added.append(exam.id)
            else:
                logging.info("Updated exam for %s - %s", course.code, exam.exam_date)
                updated.append(exam.id)

            # Add additional info that might have changed:
            if duration:
                exam.duration = duration

            if comment:
                exam.comment = comment

            if typename:
                # TODO(adamcik): use memoized helper to fetch?
                exam_type, created = ExamType.objects.get_or_create(code=typename)

                if long_typename and not exam_type.name:
                    exam_type.name = long_typename
                    exam_type.save()

                exam.type = exam_type

            exam.save()

        seen_exams = added+updated
        to_delete = list(Exam.objects.filter(course__semester=semester))
        to_delete = filter(lambda e: e.id not in seen_exams, to_delete)

        logging.info('Added %d exams', len(added))
        logging.info('Updated %d exams', len(updated))

        return to_delete
