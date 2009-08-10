# Copyright 2008, 2009 Thomas Kongevold Adamcik

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

from django.db import models, connection
from django.db.models import Q

from plan.common.utils import build_search

class LectureManager(models.Manager):
    def get_lectures(self, year, semester_type, slug=None, week=None, course=None):
        """
            Get all lectures for userset during given period.

            To do this we need to pull in a bunch of extra tables and manualy join them
            in the where cluase. The first element in the custom where is the important
            one that limits our results, the rest are simply meant for joining.
        """

        if not slug and not course:
            raise Exception('Invalid invocation of get_lectures')
        elif slug and course:
            raise Exception('Invalid invocation of get_lectures')

        where = [
            'common_userset_groups.group_id = common_group.id',
            'common_userset_groups.userset_id = common_userset.id',
            'common_group.id = common_lecture_groups.group_id',
            'common_lecture_groups.lecture_id = common_lecture.id'
        ]
        tables = [
            'common_userset_groups',
            'common_group',
            'common_lecture_groups'
        ]

        select = {
            'alias': 'common_userset.name',
            'exclude': '''
                EXISTS (SELECT 1
                 FROM common_userset_exclude WHERE
                 common_userset_exclude.userset_id = common_userset.id AND
                 common_userset_exclude.lecture_id = common_lecture.id)''',
            'show_week': '%s',
        }

        if week:
            select['show_week'] = '''
                EXISTS (SELECT 1 FROM common_week w WHERE
                    w.lecture_id = common_lecture.id AND w.number = %s)'''

        if slug:
            filter = {
                'course__userset__slug': slug,
                'course__semester__year__exact': year,
                'course__semester__type__exact': semester_type,
            }
        else:
            filter = {
                'course__name': course,
                'course__semester__year__exact': year,
                'course__semester__type__exact': semester_type,
            }
            where = []
            tables = []
            select['alias'] = 'NULL'
            select['exclude'] = 'False'

        related = [
            'type__name',
            'course__name',
        ]

        order = [
            'course__name',
            'day',
            'start',
            'type__name',
        ]

        params = [week or True]

        return  self.get_query_set().filter(**filter).\
                    distinct().\
                    select_related(*related).\
                    extra(where=where, tables=tables, select=select, select_params=params).\
                    order_by(*order)

class DeadlineManager(models.Manager):
    def get_deadlines(self, year, semester_type, slug):
        return self.get_query_set().filter(
                userset__slug=slug,
                userset__course__semester__year__exact=year,
                userset__course__semester__type__exact=semester_type,
            ).select_related(
                'userset__course',
                'userset__name',
            ).extra(select={
                'alias': 'common_userset.name',
            }).order_by(
                'date',
                'time',
            )

class ExamManager(models.Manager):
    def get_exams(self, year, semester_type, slug=None, course=None):
        if not slug and not course:
            raise Exception('Invalid invocation of get_exams')
        elif slug and course:
            raise Exception('Invalid invocation of get_exams')

        if slug:
            exam_filter = {
                'course__userset__slug': slug,
                'course__semester__year__exact': year,
                'course__semester__type__exact': semester_type,
            }
            select = {'alias': 'common_userset.name'}
        else:
            exam_filter = {
                'course__name': course,
                'course__semester__year__exact': year,
                'course__semester__type__exact': semester_type,
            }
            select = {}

        return self.get_query_set().filter(**exam_filter).select_related(
                'course',
                'type',
            ).extra(
                select=select
            ).order_by('handout_date', 'handout_time',
                    'exam_date', 'exam_time')

class CourseManager(models.Manager):
    def get_courses(self, year, semester_type, slug):
        course_filter = {
            'userset__slug': slug,
            'userset__course__semester__year__exact': year,
            'userset__course__semester__type__exact': semester_type,
        }
        return self.get_query_set().filter(**course_filter). \
            extra(select={'alias': 'common_userset.name'}).distinct().\
            order_by('name')

    def get_courses_with_exams(self, year, semester_type):
        cursor = connection.cursor()

        cursor.execute('''
            SELECT c.id as id, c.code, c.name, c.points,
                   e.exam_date, e.exam_time, et.code, et.name,
                   e.handout_date, e.handout_time
            FROM common_course c
            JOIN common_semester s ON
                (c.semester_id = s.id)
            LEFT OUTER JOIN common_exam e ON
                (e.course_id = c.id)
            LEFT OUTER JOIN common_examtype et ON
                (e.type_id = et.id)
            WHERE s.year = %s AND s.type = %s
            ORDER BY c.name, e.exam_date, e.exam_time, et.code;
        ''', [year, semester_type])

        return cursor.fetchall()

    def search(self, year, semester_type, query, limit=10):
        search_filter = build_search(query, ['code__icontains',
                                             'name__icontains',
                                             'userset__name__exact'])

        qs = self.get_query_set()
        qs = qs.filter(search_filter)
        qs = qs.filter(semester__year__exact=year,
                       semester__type__exact=semester_type)
        qs = qs.distinct()
        qs = qs.order_by('code')

        return qs[:limit]


class UserSetManager(models.Manager):
    def get_usersets(self, year, semester_type, slug):
        return self.get_query_set().filter(
                student__slug=slug,
                student__semester__year__exact=year,
                student__semester__type__exact=semester_type,
                course__semester__year__exact=year,
                course__semester__type__exact=semester_type,
            ).select_related(
                'course__code',
            ).order_by('student__slug', 'course__code')
