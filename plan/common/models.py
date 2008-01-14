from django.db import models

class Type(models.Model):
    name = models.CharField(max_length=100)

    def __unicode__(self):
        return self.name

    class Admin:
        pass

class Room(models.Model):
    name = models.CharField(max_length=100)

    def __unicode__(self):
        return self.name

    class Admin:
        pass

class Week(models.Model):
    first = models.PositiveSmallIntegerField()
    last = models.PositiveSmallIntegerField()
    lecture = models.ForeignKey('Lecture')

    def __unicode__(self):
        return u'Week %d-%d for %s' % (self.first, self.last, self.lecture)

    class Admin:
        pass

class Course(models.Model):
    name = models.CharField(max_length=100)
    # parallell

    def __unicode__(self):
        return self.name

    class Admin:
        pass

class Lecture(models.Model):
    START = [(i, '%02d:15' % i) for i in range(8,21)]
    END = [(i, '%02d:00' % i) for i in range(9,22)]

    DAYS = (
        (0, 'Monday'),
        (1, 'Tirsdag'),
        (2, 'Wensday'),
        (3, 'Thursday'),
        (4, 'Friday'),
    )

    type = models.ManyToManyField(Type)

    day = models.PositiveSmallIntegerField(choices=DAYS)
    first_period = models.PositiveSmallIntegerField(choices=START)
    last_period  = models.PositiveSmallIntegerField(choices=END)

    course = models.ManyToManyField(Course)

    room = models.ForeignKey(Room)

    def __unicode__(self):
        return u'%d: %s-%s on %s' % (self.id, self.get_first_period_display(), self.get_last_period_display(), self.day)

    class Admin:
        pass
