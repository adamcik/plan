from django.db import models

class UserSet(models.Model):
    slug = models.SlugField()
    courses = models.ForeignKey('Course')
    parallels = models.ForeignKey('Parallel')

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

class Semester(models.Model):
    SPRING = '1'
    FALL = '2'

    TYPES = (
        (SPRING, 'spring'),
        (FALL, 'fall'),
    )
    
    year = models.PositiveSmallIntegerField()
    type = models.PositiveSmallIntegerField(choices=TYPES)
    def __unicode__(self):
        return '%s %s' % (self.get_type_display(), self.year)

class Course(models.Model):
    name = models.CharField(max_length=100, unique=True)
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

    type = models.ManyToManyField(Type)
    parallel = models.ManyToManyField(Parallel)
    course = models.ForeignKey(Course)
    room = models.ForeignKey(Room)
    semester = models.ForeignKey(Semester)

    day = models.PositiveSmallIntegerField(choices=DAYS)
    first_period = models.PositiveSmallIntegerField(choices=START)
    last_period  = models.PositiveSmallIntegerField(choices=END)


    def __unicode__(self):
        return u'%s: %s-%s on %s' % (self.course, self.get_first_period_display(), self.get_last_period_display(), self.get_day_display())
