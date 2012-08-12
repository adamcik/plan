# This file is part of the plan timetable generator, see LICENSE for details.

import datetime

from django.conf import settings
from django.db import models
from django.db import connection
from django.template import defaultfilters as filters
from django.utils import dates
from django.utils import translation
from django.contrib.auth.models import User

from plan.common.managers import (LectureManager, ExamManager, CourseManager,
                                  SubscriptionManager, SemesterManager)

# To allow for overriding of the codes idea of now() for tests
now = datetime.datetime.now
today= datetime.date.today

# Setup common alias for translation
_ = translation.ugettext_lazy


class Student(models.Model):
    slug = models.SlugField(_('Slug'), unique=True)
    show_deadlines = models.BooleanField(_('Show deadlines'), default=False)

    class Meta:
        verbose_name = _('Student')
        verbose_name_plural = _('Students')

    def __unicode__(self):
        return self.slug


class Subscription(models.Model):
    student = models.ForeignKey(Student)
    course = models.ForeignKey('Course')

    alias = models.CharField(_('Alias'), max_length=50, blank=True)
    added = models.DateTimeField(_('Added'), auto_now_add=True)

    groups = models.ManyToManyField('Group', null=True)
    exclude = models.ManyToManyField('Lecture', null=True,
        related_name='excluded_from')

    objects = SubscriptionManager()

    class Meta:
        unique_together = (('student', 'course'),)

        verbose_name = _('Subscription')
        verbose_name_plural = _('Subscriptions')

    def __unicode__(self):
        return u'%s - %s' % (self.student, self.course)

    @staticmethod
    def get_groups(year, semester_type, slug):
        tmp = {}

        group_list = Group.objects.filter(
                subscription__student__slug=slug,
                subscription__course__semester__year__exact=year,
                subscription__course__semester__type__exact=semester_type,
            ).extra(select={
                'subscription_id': 'common_subscription.id',
                'group_id': 'common_group.id',
            }).values_list('subscription_id', 'group_id').distinct().order_by('code')

        for subscription, group in group_list:
            if subscription not in tmp:
                tmp[subscription] = []
            tmp[subscription].append(group)

        return tmp


# TODO(adamcik): get rid of optional since it can't be imported?
class LectureType(models.Model):
    code = models.CharField(_('Code'), max_length=20, null=True, unique=True)
    name = models.CharField(_('Name'), max_length=100, unique=True)
    optional = models.BooleanField(_('Optional'))

    def __unicode__(self):
        return self.name

    class Meta:
        verbose_name = _('Lecture type')
        verbose_name_plural = _('Lecture types')


class Room(models.Model):
    code = models.CharField(_('Code'), max_length=20, null=True, unique=True)
    name = models.CharField(_('Name'), max_length=100)
    url = models.URLField(_('URL'), verify_exists=False, default='')

    def __unicode__(self):
        return u'%s (%s)' % (self.name, self.code)

    class Meta:
        verbose_name = _('Room')
        verbose_name_plural = _('Rooms')
        unique_together = ('code', 'name')


# TODO(adamcik): add url.
class Group(models.Model):
    DEFAULT = 'Other'

    code = models.CharField(_('Code'), max_length=20, unique=True, null=True)
    name = models.CharField(_('Name'), max_length=100, null=True)
    url = models.URLField(_('URL'), verify_exists=False, default='')

    def __unicode__(self):
        return self.code

    class Meta:
        verbose_name = _('Group')
        verbose_name_plural = _('Groups')


# TODO(adamcik): link to groups with required field on intermediate. This
# field would indicate if the course is mandidtory for a given group might also
# be an idea to add the year/semester it is expected you take the course?
class Course(models.Model):
    code = models.CharField(_('Code'), max_length=100)
    semester = models.ForeignKey('Semester')

    name = models.TextField(_('Name'))
    version = models.CharField(_('Version'), max_length=20, null=True)

    url = models.URLField(_('URL'), verify_exists=False)
    syllabus = models.URLField(_('URL'), verify_exists=False)
    points = models.DecimalField(_('Points'), decimal_places=2, max_digits=5, null=True)

    objects = CourseManager()

    class Meta:
        verbose_name = _('Course')
        verbose_name_plural = _('Courses')

        unique_together = [('code', 'semester', 'version')]

    def __unicode__(self):
        if self.version:
            name = u'-'.join([self.code, self.version])
        else:
            name = self.code

        if self.semester:
            return u'%-12s - %s' % (name, self.semester)

        return name

    @property
    def short_name(self):
        if self.version:
            return u'-'.join([self.code, self.version])
        return self.code

    @staticmethod
    def get_stats(semester=None, limit=15):
        if hasattr(semester, 'pk'):
            semester_id = semester.pk
        else:
            semester_id = semester

        slug_count = int(Student.objects.filter(subscription__course__semester=semester).distinct().count())
        subscription_count = int(Subscription.objects.filter(course__semester=semester).count())
        course_count = int(Course.objects.filter(subscription__course__semester=semester).values('name').distinct().count())

        cursor = connection.cursor()
        cursor.execute('''
            SELECT COUNT(*) as num, c.id, c.code, c.name FROM
                common_subscription u JOIN common_course c ON (c.id = u.course_id)
            WHERE c.semester_id = %s
            GROUP BY c.id, c.code, c.name
            ORDER BY num DESC
            LIMIT %s''', [semester_id, limit])

        return {
            'slug_count': slug_count,
            'course_count': course_count,
            'subscription_count': subscription_count,
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
            }).values_list('course_id', 'group_id', 'code').distinct().order_by('code')

        for course, group, code in group_list:
            if course not in tmp:
                tmp[course] = []
            tmp[course].append((group, code))

        return tmp


class Semester(models.Model):
    SPRING = 'spring'
    FALL = 'fall'

    SEMESTER_TYPES = (
        (SPRING, _('spring')),
        (FALL, _('fall')),
    )

    SEMESTER_SLUG = (
        (SPRING, translation.pgettext_lazy('slug', 'spring')),
        (FALL, translation.pgettext_lazy('slug', 'fall')),
    )

    year = models.PositiveSmallIntegerField(_('Year'))
    type = models.CharField(_('Type'), max_length=10, choices=SEMESTER_TYPES)

    objects = SemesterManager()

    class Meta:
        verbose_name = _('Semester')
        verbose_name_plural = _('Semesters')

        unique_together = [('year', 'type')]

    def __init__(self, *args, **kwargs):
        super(Semester, self).__init__(*args, **kwargs)

        slug_map = dict((v, k) for k, v in self.SEMESTER_SLUG)

        if self.year:
            self.year = int(self.year)
        if self.type in slug_map:
            self.type = slug_map[self.type]

    def __unicode__(self):
        return u'%s %s' % (self.get_type_display(), self.year)

    @property
    def slug(self):
        return self.localize(self.type)

    @classmethod
    def localize(cls, semester_type):
        return dict(cls.SEMESTER_SLUG)[semester_type]

    def get_first_day(self):
        return datetime.date(
            self.year, *settings.TIMETABLE_SEMESTERS[self.type][0])

    def get_last_day(self):
        return datetime.date(
            self.year, *settings.TIMETABLE_SEMESTERS[self.type][1])

    def next(self):
        if self.type == self.SPRING:
            return Semester(year=self.year, type=self.FALL)
        return Semester(year=self.year+1, type=self.SPRING)

    @property
    def is_current(self):
        return self.get_first_day() <= today() <= self.get_last_day()

    # TODO(adamcik): this is scraper specific...
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
            current_time += datetime.timedelta(weeks=2) # FIXME to low for summer

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
    name = models.CharField(_('Name'), max_length=100, null=True)

    def __unicode__(self):
        if self.name:
            return self.name
        return self.code

    class Meta:
        verbose_name = _('Exam type')
        verbose_name_plural = _('Exam types')


class Exam(models.Model):
    course = models.ForeignKey(Course)
    type = models.ForeignKey(ExamType, null=True)
    combination = models.CharField(_('Combination'), max_length=50, null=True)

    exam_date = models.DateField(_('Exam date'), null=True)
    exam_time = models.TimeField(_('Exam time'), null=True)

    handout_date = models.DateField(_('Handout date'), null=True)
    handout_time = models.TimeField(_('Handout time'), null=True)

    duration = models.DecimalField(_('Duration'), null=True, max_digits=5,
                                     decimal_places=2, help_text=_('Duration in hours'))
    url = models.URLField(_('URL'), verify_exists=False, default='')

    objects = ExamManager()

    class Meta:
        verbose_name = _('Exam')
        verbose_name_plural = _('Exams')

    def __unicode__(self):
        return  u'%s %s - %s' % (self.course.code, self.combination, self.exam_date)


class Week(models.Model):
    NUMBER_CHOICES = [(x, x) for x in range(1, 53)]

    lecture = models.ForeignKey('Lecture', related_name='weeks')
    number = models.PositiveIntegerField(_('Week number'), choices=NUMBER_CHOICES)

    class Meta:
        unique_together = [('lecture', 'number')]

        verbose_name = _('Lecture week')
        verbose_name_plural = _('Lecture weeks')

    def __unicode__(self):
        return u'%s week %d' % (self.lecture, self.number)


class Lecturer(models.Model):
    name = models.CharField(_('Name'), max_length=200, unique=True)

    class Meta:
        verbose_name = _('Lecturer')
        verbose_name_plural = _('Lecturers')

    def __unicode__(self):
        return self.name


class Lecture(models.Model):
    DAYS = [(i, dates.WEEKDAYS[i]) for i in xrange(5)]

    course = models.ForeignKey(Course)

    day = models.PositiveSmallIntegerField(_('Week day'), choices=DAYS)

    start = models.TimeField(_('Start time'))
    end = models.TimeField(_('End time'))

    rooms = models.ManyToManyField(Room, null=True)
    type = models.ForeignKey(LectureType, null=True)
    groups = models.ManyToManyField(Group, null=True)
    lecturers = models.ManyToManyField(Lecturer, null=True)

    objects = LectureManager()

    class Meta:
        verbose_name = _('Lecture')
        verbose_name_plural = _('Lecture')

    def __unicode__(self):
        return u'%4d %10s %s-%s %s on %3s' % (
            self.id,
            self.course.short_name,
            filters.time(self.start),
            filters.time(self.end),
            self.type,
            self.get_day_display()[:3])

    @property
    def short_name(self):
        return u'%s-%s on %s' % (
                filters.time(self.start),
                filters.time(self.end),
                self.get_day_display()
            )

    @staticmethod
    def get_related(model, lectures, fields=None, use_extra=True):
        tmp = {}

        if not lectures:
            return tmp

        if fields is None:
            fields = ['name']

        name = model._meta.object_name.lower()

        objects = model.objects.filter(lecture__in=lectures)

        if use_extra:
            objects = objects.extra(select={
                    'lecture_id': 'common_lecture_%ss.lecture_id' % name,
                })
        object_list = objects.values_list('lecture_id', *fields)

        for obj in object_list:
            lecture = obj[0]

            if lecture not in tmp:
                tmp[lecture] = []

            if len(fields) == 1:
                tmp[lecture].append(obj[1])
            else:
                tmp[lecture].append(dict(map(lambda x, y: (x, y), fields, obj[1:])))

        return tmp


# TODO(adamcik): This has been deprecated, leaving the data around for now.
class Deadline(models.Model):
    subscription = models.ForeignKey('Subscription')
    task = models.CharField(_('Task'), max_length=255)
    date = models.DateField(_('Due date'))
    time = models.TimeField(_('Time'), null=True)
    done = models.DateTimeField(_('Done'), null=True)
