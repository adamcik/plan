from datetime import datetime, timedelta, time

from django.db import models, connection
from django.http import Http404
from django.template.defaultfilters import time as time_filter

from plan.common.managers import LectureManager, DeadlineManager, \
        ExamManager, CourseManager, UserSetManager

# To allow for overriding of the codes idea of now() for tests
now = datetime.now

class UserSet(models.Model):
    slug = models.SlugField()
    course = models.ForeignKey('Course')

    groups = models.ManyToManyField('Group', blank=True, null=True)
    name = models.CharField(max_length=50, blank=True)

    added = models.DateTimeField(auto_now_add=True)
    exclude = models.ManyToManyField('Lecture', blank=True, null=True,
                                     related_name='excluded_from')

    objects = UserSetManager()

    class Meta:
        unique_together = (('slug', 'course'),)

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
    DEFAULT = 'Other'

    name = models.CharField(max_length=100, unique=True)

    def __unicode__(self):
        return self.name

class Course(models.Model):
    name = models.CharField(max_length=100)
    full_name = models.TextField(blank=True)
    url = models.URLField(verify_exists=False, blank=True)
    points = models.DecimalField(decimal_places=2, max_digits=5, null=True)
    version = models.CharField(max_length=20, blank=True, null=True)

    semester = models.ForeignKey('Semester', null=True, blank=True)

    objects = CourseManager()

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
            return u'-'.join([self.name, self.version])
        return self.name

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

    year = models.PositiveSmallIntegerField()
    type = models.PositiveSmallIntegerField(choices=TYPES)

    class Meta:
        unique_together = [('year', 'type'),]

    def __init__(self, *args, **kwargs):
        super(Semester, self).__init__(*args, **kwargs)

        if int != type(self.type) and self.type is not None \
                and not self.type.isdigit():
            try:
                lookup = dict(map(lambda a: (a[1], a[0]), self.TYPES))
                self.type = lookup[self.type]
            except KeyError:
                raise Http404

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
            return datetime(self.year, 6, 30)
        else:
            return datetime(self.year, 12, 31)

    def next(self):
        if self.type == self.SPRING:
            return Semester(year=self.year, type=self.FALL)
        return Semester(year=self.year+1, type=self.SPRING)

    def get_weeks(self):
        return xrange(0,53)

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

    objects = ExamManager()

    def __unicode__(self):
        return  u'%s (%s)' % (self.course, self.type)

class Week(models.Model):
    NUMBER_CHOICES = [(x, x) for x in range(1, 53)]

    lecture = models.ForeignKey('Lecture')
    number = models.PositiveIntegerField(choices=NUMBER_CHOICES)

    class Meta:
        unique_together = [('lecture', 'number')]

    def __unicode__(self):
        return u'%s week %d' % (self.lecture, self.number)

class Lecturer(models.Model):
    name = models.CharField(max_length=200)

    def __unicode__(self):
        return self.name

class Lecture(models.Model):
    DAYS = (
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
#        (5, 'Saturday'),
#        (6, 'Sunday'),
    )

    course = models.ForeignKey(Course)

    day = models.PositiveSmallIntegerField(choices=DAYS)

    start = models.TimeField()
    end = models.TimeField()

    rooms = models.ManyToManyField(Room, blank=True, null=True)
    type = models.ForeignKey(Type, blank=True, null=True)
    groups = models.ManyToManyField(Group, blank=True, null=True)
    lecturers = models.ManyToManyField(Lecturer, blank=True, null=True)

    objects = LectureManager()

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
    userset = models.ForeignKey('UserSet')

    date = models.DateField(default=now().date()+timedelta(days=7))
    time = models.TimeField(null=True, blank=True)
    task = models.CharField(max_length=255)

    objects = DeadlineManager()

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
