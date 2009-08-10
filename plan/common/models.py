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

from datetime import datetime, timedelta, time

from django.db import models, connection
from django.http import Http404
from django.template.defaultfilters import time as time_filter
from django.utils.translation import ugettext_lazy as _

from plan.common.managers import LectureManager, DeadlineManager, \
        ExamManager, CourseManager, UserSetManager

# To allow for overriding of the codes idea of now() for tests
now = datetime.now

class UserSet(models.Model):
    slug = models.SlugField(_('Slug'))

    course = models.ForeignKey('Course')
    groups = models.ManyToManyField('Group', blank=True, null=True)

    name = models.CharField(_('Alias'), max_length=50, blank=True)

    added = models.DateTimeField(_('Added'), auto_now_add=True)

    exclude = models.ManyToManyField('Lecture', blank=True, null=True,
        related_name='excluded_from')

    objects = UserSetManager()

    class Meta:
        unique_together = (('slug', 'course'),)

        verbose_name = _('Userset')
        verbose_name_plural = _('Userset')

    def __unicode__(self):
        return u'%s - %s' % (self.slug, self.course)

    @staticmethod
    def get_groups(year, semester_type, slug):
        tmp = {}

        group_list = Group.objects.filter(
                userset__slug=slug,
                userset__course__semester__year__exact=year,
                userset__course__semester__type__exact=semester_type,
            ).extra(select={
                'userset_id': 'common_userset.id',
                'group_id': 'common_group.id',
            }).values_list('userset_id', 'group_id').distinct()

        for userset, group in group_list:
            if userset not in tmp:
                tmp[userset] = []
            tmp[userset].append(group)

        return tmp

class LectureType(models.Model):
    name = models.CharField(_('Name'), max_length=100, unique=True)
    optional = models.BooleanField(_('Optional'))

    def __unicode__(self):
        return self.name

    class Meta:
        verbose_name = _('Lecture type')
        verbose_name_plural = _('Lecture types')

class Room(models.Model):
    name = models.CharField(_('Name'), max_length=100, unique=True)

    def __unicode__(self):
        return self.name

    class Meta:
        verbose_name = _('Room')
        verbose_name_plural = _('Rooms')

class Group(models.Model):
    DEFAULT = 'Other'

    name = models.CharField(_('Name'), max_length=100, unique=True)

    def __unicode__(self):
        return self.name

    class Meta:
        verbose_name = _('Group')
        verbose_name_plural = _('Groups')

class Course(models.Model):
    name = models.CharField(_('Code'), max_length=100)
    full_name = models.TextField(_('Name'), blank=True)
    url = models.URLField(_('URL'), verify_exists=False, blank=True)
    points = models.DecimalField(_('Points'), decimal_places=2, max_digits=5, null=True, blank=True)
    version = models.CharField(_('Version'), max_length=20, blank=True, null=True)

    semester = models.ForeignKey('Semester')

    objects = CourseManager()

    class Meta:
        verbose_name = _('Course')
        verbose_name_plural = _('Courses')

    def get_url(self):
        values = self.__dict__
        for key in values.keys():
            if type(values[key]) in [unicode, str]:
                values['%s_lower' % key] = values.get(key, '').lower()
                values['%s_upper' % key] = values.get(key, '').upper()
            else:
                values['%s_lower' % key] = values[key]
                values['%s_upper' % key] = values[key]

        return self.url % values

    def __unicode__(self):
        if self.version:
            name = u'-'.join([self.name, self.version])
        else:
            name = self.name

        if self.semester:
            return u'%s - %s' % (name, self.semester)

        return name

    @staticmethod
    def get_stats(semester=None, limit=15):
        if hasattr(semester, 'pk'):
            semester_id = semester.pk
        else:
            semester_id = semester

        slug_count = int(UserSet.objects.filter(course__semester=semester).values('slug').distinct().count())
        subscription_count = int(UserSet.objects.filter(course__semester=semester).count())
        deadline_count = int(Deadline.objects.filter(userset__course__semester=semester).count())
        course_count = int(Course.objects.filter(userset__course__semester=semester).values('name').distinct().count())

        cursor = connection.cursor()
        cursor.execute('''
            SELECT COUNT(*) as num, c.id, c.name, c.full_name FROM
                common_userset u JOIN common_course c ON (c.id = u.course_id)
            WHERE c.semester_id = %s
            GROUP BY c.id, c.name, c.full_name
            ORDER BY num DESC
            LIMIT %s''', [semester_id, limit])

        return {
            'slug_count': slug_count,
            'course_count': course_count,
            'subscription_count': subscription_count,
            'deadline_count': deadline_count,
            'stats': cursor.fetchall(),
            'limit': limit,
        }

    @staticmethod
    def get_groups(year, semester_type, courses):
        tmp = {}

        group_list = Group.objects.filter(
                lecture__course__in=courses,
                lecture__course__semester__year__exact=year,
                lecture__course__semester__type__exact=semester_type,
            ).extra(select={
                'course_id': 'common_lecture.course_id',
                'group_id': 'common_group.id',
            }).values_list('course_id', 'group_id', 'name').distinct()

        for course, group, name in group_list:
            if course not in tmp:
                tmp[course] = []
            tmp[course].append((group, name))

        return tmp

class Semester(models.Model):
    SPRING = 'spring'
    FALL = 'fall'

    SEMESTER_TYPES = (
        (SPRING, _('spring')),
        (FALL, _('fall')),
    )

    year = models.PositiveSmallIntegerField(_('Year'))
    type = models.CharField(_('Type'), max_length=10, choices=SEMESTER_TYPES)

    class Meta:
        unique_together = [('year', 'type'),]

        verbose_name = _('Semester')
        verbose_name_plural = _('Semesters')

    def __init__(self, *args, **kwargs):
        super(Semester, self).__init__(*args, **kwargs)

        if self.year:
            self.year = int(self.year)

    def __unicode__(self):
        return u'%s %s' % (self.get_type_display(), self.year)

    def get_first_day(self):
        if self.type == self.SPRING:
            return datetime(self.year, 1, 1)
        else:
            return datetime(self.year, 6, 30)

    def get_last_day(self):
        if self.type == self.SPRING:
            return datetime(self.year, 7, 1)
        else:
            return datetime(self.year, 12, 31)

    def next(self):
        if self.type == self.SPRING:
            return Semester(year=self.year, type=self.FALL)
        return Semester(year=self.year+1, type=self.SPRING)

    @property
    def prefix(self):
        if self.type == self.SPRING:
            return 'v%s' % str(self.year)[-2:]
        else:
            return 'h%s' % str(self.year)[-2:]

    @staticmethod
    def current(from_db=False, early=False):
        current_time = now()

        if early:
            current_time += timedelta(weeks=2)

        # Default to current semester
        if current_time.month <= 6:
            current = Semester(type=Semester.SPRING, year=current_time.year)
        else:
            current = Semester(type=Semester.FALL, year=current_time.year)

        if not from_db:
            return current

        return Semester.objects.get(year=current.year, type=current.type)

class ExamType(models.Model):
    code = models.CharField(_('Code'), max_length=20, unique=True)
    name = models.CharField(_('Name'), max_length=100, blank=True, null=True)

    def __unicode__(self):
        if self.name:
            return self.name
        return self.code

    class Meta:
        verbose_name = _('Exam type')
        verbose_name_plural = _('Exam types')

class Exam(models.Model):
    exam_date = models.DateField(_('Exam date'), blank=True, null=True)
    exam_time = models.TimeField(_('Exam time'), blank=True, null=True)

    handout_date = models.DateField(_('Handout date'), blank=True, null=True)
    handout_time = models.TimeField(_('Handout time'), blank=True, null=True)

    duration = models.PositiveSmallIntegerField(_('Duration'), blank=True, null=True,
            help_text=_('Duration in hours'))

    comment = models.TextField(_('Comment'), blank=True)

    type = models.ForeignKey(ExamType, null=True, blank=True)

    course = models.ForeignKey(Course)

    objects = ExamManager()

    class Meta:
        verbose_name = _('Exam')
        verbose_name_plural = _('Exams')

    def __unicode__(self):
        return  u'%s (%s)' % (self.course, self.type)

class Week(models.Model):
    NUMBER_CHOICES = [(x, x) for x in range(1, 53)]

    lecture = models.ForeignKey('Lecture')
    number = models.PositiveIntegerField(_('Week number'), choices=NUMBER_CHOICES)

    class Meta:
        unique_together = [('lecture', 'number')]

        verbose_name = _('Lecture week')
        verbose_name_plural = _('Lecture weeks')

    def __unicode__(self):
        return u'%s week %d' % (self.lecture, self.number)

class Lecturer(models.Model):
    name = models.CharField(_('Name'), max_length=200)

    class Meta:
        verbose_name = _('Lecturer')
        verbose_name_plural = _('Lecturers')

    def __unicode__(self):
        return self.name

class Lecture(models.Model):
    DAYS = (
        (0, _('Monday')),
        (1, _('Tuesday')),
        (2, _('Wednesday')),
        (3, _('Thursday')),
        (4, _('Friday')),
#        (5, 'Saturday'),
#        (6, 'Sunday'),
    )

    course = models.ForeignKey(Course)

    day = models.PositiveSmallIntegerField(_('Week day'), choices=DAYS)

    start = models.TimeField(_('Start time'))
    end = models.TimeField(_('End time'))

    rooms = models.ManyToManyField(Room, blank=True, null=True)
    type = models.ForeignKey(LectureType, blank=True, null=True)
    groups = models.ManyToManyField(Group, blank=True, null=True)
    lecturers = models.ManyToManyField(Lecturer, blank=True, null=True)

    objects = LectureManager()

    class Meta:
        verbose_name = _('Lecture')
        verbose_name_plural = _('Lecture')

    def __unicode__(self):
        return u'%4d %10s %s-%s on %3s' % (
            self.id,
            self.course,
            time_filter(self.start),
            time_filter(self.end),
            self.get_day_display()[:3])

    @staticmethod
    def get_related(model, lectures, field='name', use_extra=True):
        tmp = {}

        if not lectures:
            return tmp

        name = model._meta.object_name.lower()

        objects = model.objects.filter(lecture__in=lectures)

        if use_extra: 
            objects = objects.extra(select={
                    'lecture_id': 'common_lecture_%ss.lecture_id' % name,
                }).values_list('lecture_id', field)

        object_list = objects.values_list('lecture_id', field)

        for lecture, name in object_list:
            if lecture not in tmp:
                tmp[lecture] = []
            tmp[lecture].append(name)

        return tmp

class Deadline(models.Model):
    DEFALULT_DATE = lambda: now().date()+timedelta(days=7)

    userset = models.ForeignKey('UserSet')

    date = models.DateField(_('Due date'), default=DEFALULT_DATE)
    time = models.TimeField(_('Time'), null=True, blank=True)
    task = models.CharField(_('Task'), max_length=255)

    objects = DeadlineManager()

    class Meta:
        verbose_name = _('Deadline')
        verbose_name_plural = _('Deadlines')

    def __unicode__(self):
        if self.time:
            return u'%s %s- %s %s' % (self.userset, self.userset.slug,
                                     self.date, self.time)
        else:
            return u'%s %s- %s' % (self.userset, self.userset.slug, self.date)

    @property
    def datetime(self):
        if self.time:
            return datetime.combine(self.date, self.time)
        else:
            return datetime.combine(self.date, time())

    @property
    def seconds(self):
        td = self.datetime - now()

        return td.days * 3600 * 24 + td.seconds

    @property
    def expired(self):
        if self.time:
            return datetime.combine(self.date, self.time) < now()
        else:
            return self.date <= now().date()

    @property
    def slug(self):
        return self.userset.slug

    @property
    def course(self):
        return self.userset.course
