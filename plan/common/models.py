from datetime import datetime
from urllib import quote as urlquote

from django.db import models

class UserSet(models.Model):
    slug = models.SlugField()
    course = models.ForeignKey('Course')
    semester = models.ForeignKey('Semester')
    groups = models.ManyToManyField('Group', blank=True, null=True)

    exclude = models.ManyToManyField('Lecture', blank=True, null=True, related_name='excluded_from')

    class Meta:
        unique_together = (('slug', 'course'),)
        ordering = ('slug', 'course')

    def __unicode__(self):
        return '%s - %s' % (self.slug, self.course)

class Type(models.Model):
    name = models.CharField(max_length=100, unique=True)
    optional = models.BooleanField()

    def __unicode__(self):
        return self.name

class Room(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __unicode__(self):
        return self.name

class Group(models.Model):
    DEFAULT = 'Unknown'

    name = models.CharField(max_length=100, unique=True)

    def __unicode__(self):
        return self.name

class Course(models.Model):
    name = models.CharField(max_length=100, unique=True)
    full_name = models.TextField(blank=True)
    url = models.URLField(verify_exists=False, blank=True)

    def __unicode__(self):
        return self.name

    class Meta:
        ordering = ('name',)

class Semester(models.Model):
    SPRING = 0
    FALL = 1

    TYPES = (
        (SPRING, 'spring'),
        (FALL, 'fall'),
    )
    URL_MAP = (
        (SPRING, 'v'),
        (FALL, 'h'),
    )

    year = models.PositiveSmallIntegerField(choices=[(x,x) for x in range(datetime.now().year-1,datetime.now().year+2)])
    type = models.PositiveSmallIntegerField(choices=TYPES)

    def __unicode__(self):
        return '%s %s' % (self.get_type_display(), self.year)

    class Meta:
        ordering = ('-year', '-type')

    def get_exam_page(self):
        url = 'http://www.ntnu.no/eksamen/plan/%s%s/'

        return url % (str(self.year)[-2:], dict(self.URL_MAP)[self.type])

    def get_lecture_page(self, course):
        url = 'http://www.ntnu.no/studieinformasjon/timeplan/%s%s/?emnekode=%s-1'

        return url % (str(self.year)[-2:], dict(self.URL_MAP)[self.type], course.upper().strip())

    def get_course_page(self, letter):
        url = u'http://www.ntnu.no/studieinformasjon/timeplan/%s%s/?bokst=%s'

        return url % (str(self.year)[-2:], dict(self.URL_MAP)[self.type], urlquote(letter.encode('utf-8')))

    def get_first_day(self):
        if self.type == self.SPRING:
            return datetime(self.year,1,1)
        else:
            return datetime(self.year,6,30)

    def get_last_day(self):
        if self.type == self.SPRING:
            return datetime(self.year,6,30)
        else:
            return datetime(self.year,12,31)


class Exam(models.Model):
    exam_time = models.DateTimeField()
    handout_time = models.DateTimeField(blank=True, null=True)

    duration = models.PositiveSmallIntegerField(blank=True, null=True)
    comment = models.TextField(blank=True)

    type = models.CharField(max_length=1, blank=True)
    course = models.ForeignKey(Course)

    def __unicode__(self):
        if self.handout_time:
            return '%s: handout: %s, delivery: %s' % (self.course, self.handout_time, self.exam_time)
        return  '%s: %s' % (self.course, self.exam_time)

    class Meta:
        ordering = ('handout_time', 'exam_time')

class Week(models.Model):
    number = models.PositiveSmallIntegerField(choices=[(x,x) for x in range(1,53)], unique=True)

    def __unicode__(self):
        return '%d' % self.number

    class Meta:
        ordering = ('number',)

class Lecturer(models.Model):
    name = models.CharField(max_length=200)

    def __unicode__(self):
        return self.name

class Lecture(models.Model):
    START = [(i, '%02d:15' % i) for i in range(8,20)]
    END = [(i, '%02d:00' % i) for i in range(9,21)]

    DAYS = (
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
    )

    course = models.ForeignKey(Course)
    semester = models.ForeignKey(Semester)

    day = models.PositiveSmallIntegerField(choices=DAYS)

    start_time = models.PositiveSmallIntegerField(choices=START)
    end_time  = models.PositiveSmallIntegerField(choices=END)

    rooms = models.ManyToManyField(Room, blank=True, null=True)
    type = models.ForeignKey(Type, blank=True, null=True)
    weeks = models.ManyToManyField(Week, blank=True, null=True)
    groups = models.ManyToManyField(Group, blank=True, null=True)
    lecturers = models.ManyToManyField(Lecturer, blank=True, null=True)

    def __unicode__(self):
        return u'%s: %s-%s on %s' % (self.course, self.get_start_time_display(), self.get_end_time_display(), self.get_day_display())

    class Meta:
        ordering = ('course', 'day', 'start_time')
