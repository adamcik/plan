from django.db import models

class LectureManager(models.Manager):
    def get_lectures(self, slug, semester):
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
            'user_name': 'common_userset.name',
            'exclude': """common_lecture.id IN
                (SELECT common_userset_exclude.lecture_id
                 FROM common_userset_exclude WHERE
                 common_userset_exclude.userset_id = common_userset.id)""",
        }

        filter = {
            'course__userset__slug': slug,
            'course__userset__semester': semester,
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
    def get_deadlines(self, slug, semester):
        return self.get_query_set().filter(
                userset__slug=slug,
                userset__semester=semester,
            ).select_related(
                'userset__course',
                'userset__name',
            )

class ExamManager(models.Manager):
    def get_exams(self, slug, semester):
        return self.get_query_set().filter(
                exam_date__gt=semester.get_first_day(),
                exam_date__lt=semester.get_last_day(),
                course__userset__slug=slug,
                course__userset__semester=semester,
            ).select_related(
                'course__name',
                'course__full_name',
            ).extra(
                select={'user_name': 'common_userset.name'}
            )

class CourseManager(models.Manager):
    def get_courses(self, slug, semester):
        course_filter = {
            'userset__slug': slug,
            'userset__semester': semester,
        }
        return self.get_query_set().filter(**course_filter). \
            extra(select={'user_name': 'common_userset.name'}).distinct()
