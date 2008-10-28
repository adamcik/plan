from django.db import models
from django.db.models import Q

class LectureManager(models.Manager):
    def get_lectures(self, year, semester_type, slug):
        """
            Get all lectures for userset during given period.

            To do this we need to pull in a bunch of extra tables and manualy join them
            in the where cluase. The first element in the custom where is the important
            one that limits our results, the rest are simply meant for joining.
        """

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
            'exclude': """common_lecture.id IN
                (SELECT common_userset_exclude.lecture_id
                 FROM common_userset_exclude WHERE
                 common_userset_exclude.userset_id = common_userset.id)""",
        }

        filter = {
            'course__userset__slug': slug,
            'course__userset__semester__year__exact': year,
            'course__userset__semester__type__exact': semester_type,
        }

        related = [
            'type__name',
            'course__name',
        ]

        order = [
            'course__name',
            'day',
            'start_time',
            'type__name',
        ]

        return  self.get_query_set().filter(**filter).\
                    distinct().\
                    select_related(*related).\
                    extra(where=where, tables=tables, select=select).\
                    order_by(*order)

class DeadlineManager(models.Manager):
    def get_deadlines(self, year, semester_type, slug):
        return self.get_query_set().filter(
                userset__slug=slug,
                userset__semester__year__exact=year,
                userset__semester__type__exact=semester_type,
            ).select_related(
                'userset__course',
                'userset__name',
            ).extra(select={
                'alias': 'common_userset.name',
            })

class ExamManager(models.Manager):
    def get_exams(self, year, semester_type, slug, first=None, last=None):
        exam_filter = {
            'course__userset__slug': slug,
            'course__userset__semester__year__exact': year,
            'course__userset__semester__type__exact': semester_type,
        }
        if first:
            exam_filter['exam_date__gt'] = first
        if last:
            exam_filter['exam_date__lt'] = last

        return self.get_query_set().filter(**exam_filter).select_related(
                'course__name',
                'course__full_name',
            ).extra(
                select={'alias': 'common_userset.name'}
            )

class CourseManager(models.Manager):
    def get_courses(self, year, semester_type, slug):
        course_filter = {
            'userset__slug': slug,
            'userset__semester__year__exact': year,
            'userset__semester__type__exact': semester_type,
        }
        return self.get_query_set().filter(**course_filter). \
            extra(select={'alias': 'common_userset.name'}).distinct()

    def get_courses_with_exams(self, year, semester_type, first, last):
        no_exam = Q(exam__isnull=True)
        with_exam = Q(exam__exam_date__gt=first, exam__exam_date__lt=last)

        return self.get_query_set().filter(
                semesters__year__exact=year,
                semesters__type__exact=semester_type,
            ).filter(no_exam | with_exam).extra(select={
                'alias': 'common_userset.name',
                'exam_date': 'common_exam.exam_date',
                'exam_time': 'common_exam.exam_time',
                'handout_date': 'common_exam.handout_date',
                'handout_time': 'common_exam.handout_time',
                'type': 'common_exam.type',
                'type_name': 'common_exam.type_name',
            })

class UserSetManager(models.Manager):
    def get_usersets(self, year, semester_type, slug):
        return self.get_query_set().filter(
                slug=slug,
                semester__year__exact=year,
                semester__type__exact=semester_type,
            ).select_related(
                'course__name',
            )
