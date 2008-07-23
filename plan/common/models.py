from datetime import datetime

from django.db import models

class UserSet(models.Model):
    slug = models.SlugField()
    course = models.ForeignKey('Course')
    parallel = models.ForeignKey('Parallel', blank=True, null=True)

    class Meta:
        unique_together = (('slug', 'course', 'parallel'),)

class Type(models.Model):
    name = models.CharField(max_length=100, unique=True)
    def __unicode__(self):
        return self.name

class Room(models.Model):
    name = models.CharField(max_length=100, unique=True)
    def __unicode__(self):
        return self.name

class Parallel(models.Model):
    name = models.CharField(max_length=100, unique=True)
    def __unicode__(self):
        return self.name

class Course(models.Model):
    name = models.CharField(max_length=100, unique=True)
    full_name = models.TextField(blank=True)
    url = models.URLField(verify_exists=False, blank=True)

    def __unicode__(self):
        return self.name

class Lecture(models.Model):
    START = [(i, '%02d:15' % i) for i in range(8,21)]
    END = [(i, '%02d:00' % i) for i in range(9,22)]

    DAYS = (
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
    )

    SPRING = 0
    FALL = 1
    SEMESTER = (
        (SPRING, 'spring'),
        (FALL, 'fall'),
    )

    WEEKS = [(x,x) for x in range(52)]

    type = models.ManyToManyField(Type, blank=True, null=True)
    parallel = models.ManyToManyField(Parallel, blank=True, null=True)
    course = models.ForeignKey(Course)
    room = models.ForeignKey(Room, blank=True, null=True)
    year = models.PositiveSmallIntegerField(choices=[(x,x) for x in range(datetime.now().year-1,datetime.now().year+2)])
    semester = models.PositiveSmallIntegerField(choices=SEMESTER)

    day = models.PositiveSmallIntegerField(choices=DAYS)

    start_time = models.PositiveSmallIntegerField(choices=START)
    end_time  = models.PositiveSmallIntegerField(choices=END)

    start_week = models.PositiveSmallIntegerField(choices=WEEKS, blank=True, null=True)
    end_week = models.PositiveSmallIntegerField(choices=WEEKS, blank=True, null=True)

    optional = models.BooleanField(default=False)

    def __unicode__(self):
        return u'%s: %s-%s on %s' % (self.course, self.get_start_time_display(), self.get_end_time_display(), self.get_day_display())
