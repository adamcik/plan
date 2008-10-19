from datetime import datetime, timedelta, time

from django.db import models
from django.template.defaultfilters import slugify

from plan.common.managers import LectureManager

class UserSet(models.Model):
    slug = models.SlugField()
    course = models.ForeignKey('Course')
    semester = models.ForeignKey('Semester')
    groups = models.ManyToManyField('Group', blank=True, null=True)
    name = models.CharField(max_length=50, blank=True)

    added = models.DateTimeField(auto_now_add=True)
    exclude = models.ManyToManyField('Lecture', blank=True, null=True,
                                     related_name='excluded_from')

    class Meta:
        unique_together = (('slug', 'course'),)
        ordering = ('slug', 'course')

    def __unicode__(self):
        return '%s' % (self.course)

    def save(self, *args, **kwargs):
        self.name = slugify(self.name)
        super(UserSet, self).save(*args, **kwargs)

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
    points = models.DecimalField(decimal_places=2, max_digits=5, null=True)

    semesters = models.ManyToManyField('Semester', blank=True, null=True)

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

    YEAR_CURRENT = datetime.now().year
    YEAR_CHOICES = [(x, x) for x in range(YEAR_CURRENT-1, YEAR_CURRENT+2)]

    year = models.PositiveSmallIntegerField(choices=YEAR_CHOICES)
    type = models.PositiveSmallIntegerField(choices=TYPES)

    def __unicode__(self):
        return '%s %s' % (self.get_type_display(), self.year)

    class Meta:
        ordering = ('-year', '-type')

    def get_first_day(self):
        if self.type == self.SPRING:
            return datetime(self.year, 1, 1)
        else:
            return datetime(self.year, 6, 30)

    def get_last_day(self):
        if self.type == self.SPRING:
            return datetime(self.year, 6, 30)
        else:
            return datetime(self.year, 12, 31)

    @staticmethod
    def current():
        now = datetime.now()

        # Default to current semester
        if now.month <= 6:
            return Semester(type=Semester.SPRING, year=now.year)
        else:
            return Semester(type=Semester.FALL, year=now.year)



class Exam(models.Model):
    exam_date = models.DateField(blank=True, null=True)
    exam_time = models.TimeField(blank=True, null=True)

    handout_date = models.DateField(blank=True, null=True)
    handout_time = models.TimeField(blank=True, null=True)

    duration = models.PositiveSmallIntegerField(blank=True, null=True)

    comment = models.TextField(blank=True)

    type = models.CharField(max_length=1, blank=True)
    type_name = models.CharField(max_length=100, blank=True, null=True)
    course = models.ForeignKey(Course)

    def __unicode__(self):
        return  '%s (%s)' % (self.course, self.type)

    class Meta:
        ordering = ('handout_time', 'exam_time')

class Week(models.Model):
    NUMBER_CHOICES = [(x, x) for x in range(1, 53)]


    number = models.PositiveSmallIntegerField(choices=NUMBER_CHOICES,
                                              unique=True)

    def __unicode__(self):
        return '%d' % self.number

    class Meta:
        ordering = ('number',)

class Lecturer(models.Model):
    name = models.CharField(max_length=200)

    def __unicode__(self):
        return self.name

    class Meta:
        ordering = ('name',)

class Lecture(models.Model):
    START = [(i, '%02d:15' % i) for i in range(8, 20)]
    END = [(i, '%02d:00' % i) for i in range(9, 21)]

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

    objects = LectureManager()

    def __unicode__(self):
        return u'%s: %s-%s on %s' % (self.course,
                                     self.get_start_time_display(),
                                     self.get_end_time_display(),
                                     self.get_day_display())

    class Meta:
        ordering = ('course', 'day', 'start_time')

class Deadline(models.Model):
    userset = models.ForeignKey('UserSet')

    date = models.DateField(default=datetime.now().date()+timedelta(days=7))
    time = models.TimeField(null=True, blank=True)

    task = models.CharField(max_length=255)

    def get_datetime(self):
        if self.time:
            return datetime.combine(self.date, self.time)
        else:
            return datetime.combine(self.date, time())

    def get_seconds(self):
        td = self.get_datetime() - datetime.now()

        return td.days * 3600 * 24 + td.seconds

    datetime = property(get_datetime)

    def is_expired(self):
        if self.time:
            return datetime.combine(self.date, self.time) < datetime.now()
        else:
            return self.date <= datetime.now().date()
    expired = property(is_expired)

    def __unicode__(self):
        if self.time:
            return '%s %s- %s %s' % (self.userset, self.userset.slug,
                                     self.date, self.time)
        else:
            return '%s %s- %s' % (self.userset, self.userset.slug, self.date)

    class Meta:
        ordering = ('date', 'time')
