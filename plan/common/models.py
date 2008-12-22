from datetime import datetime, timedelta, time

from django.db import models, connection
from django.http import Http404

from plan.common.managers import LectureManager, DeadlineManager, \
        ExamManager, CourseManager, UserSetManager

class UserSet(models.Model):
    slug = models.SlugField()
    course = models.ForeignKey('Course')
    semester = models.ForeignKey('Semester')
    groups = models.ManyToManyField('Group', blank=True, null=True)
    name = models.CharField(max_length=50, blank=True)

    added = models.DateTimeField(auto_now_add=True)
    exclude = models.ManyToManyField('Lecture', blank=True, null=True,
                                     related_name='excluded_from')

    objects = UserSetManager()

    class Meta:
        unique_together = (('slug', 'course', 'semester'),)
        ordering = ('slug', 'course')

    def __unicode__(self):
        return u'%s - %s' % (self.slug, self.course)

    @staticmethod
    def get_groups(year, semester_type, slug):
        tmp = {}

        group_list = Group.objects.filter(
                userset__slug=slug,
                userset__semester__year__exact=year,
                userset__semester__type__exact=semester_type,
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
        return self.name

    class Meta:
        ordering = ('name',)

    @staticmethod
    def get_stats(semester=None, limit=15):
        if hasattr(semester, 'pk'):
            semester_id = semester.pk
        else:
            semester_id = semester

        cursor = connection.cursor()
        cursor.execute('''
            SELECT COUNT(*) as num, c.name, c.full_name FROM
                common_userset u JOIN common_course c ON (c.id = u.course_id)
            WHERE u.semester_id = %d
            GROUP BY c.name, c.full_name
            ORDER BY num DESC
            LIMIT %d''', [semester_id, limit])

        return cursor.fetchall()

    @staticmethod
    def get_groups(year, semester_type, courses):
        tmp = {}

        group_list = Group.objects.filter(
                lecture__course__in=courses,
                lecture__semester__year__exact=year,
                lecture__semester__type__exact=semester_type,
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

    YEAR_CURRENT = datetime.now().year
    YEAR_CHOICES = [(x, x) for x in range(YEAR_CURRENT-1, YEAR_CURRENT+2)]

    year = models.PositiveSmallIntegerField(choices=YEAR_CHOICES)
    type = models.PositiveSmallIntegerField(choices=TYPES)

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

    class Meta:
        ordering = ('year', '-type')

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

    @staticmethod
    def current(from_db=False, early=False):
        now = datetime.now()

        if early:
            now += timedelta(weeks=2)

        # Default to current semester
        if now.month <= 6:
            current = Semester(type=Semester.SPRING, year=now.year)
        else:
            current = Semester(type=Semester.FALL, year=now.year)

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
    semester = models.ForeignKey(Semester, null=True)

    objects = ExamManager()

    def __unicode__(self):
        return  u'%s (%s)' % (self.course, self.type)

    class Meta:
        ordering = ('handout_time', 'exam_time')

class Week(models.Model):
    NUMBER_CHOICES = [(x, x) for x in range(1, 53)]

    number = models.PositiveIntegerField(choices=NUMBER_CHOICES, unique=True)

    def __unicode__(self):
        return u'%d' % self.number

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

    @staticmethod
    def get_related(model, lectures, field='name'):
        tmp = {}

        if not lectures:
            return tmp

        name = model._meta.object_name.lower()

        object_list = model.objects.filter(lecture__in=lectures). \
            extra(select={
                'lecture_id': 'common_lecture_%ss.lecture_id' % name,
            }).values_list('lecture_id', field)

        for lecture, name in object_list:
            if lecture not in tmp:
                tmp[lecture] = []
            tmp[lecture].append(name)

        return tmp

class Deadline(models.Model):
    userset = models.ForeignKey('UserSet')

    date = models.DateField(default=datetime.now().date()+timedelta(days=7))
    time = models.TimeField(null=True, blank=True)
    task = models.CharField(max_length=255)

    objects = DeadlineManager()

    class Meta:
        ordering = ('date', 'time')

    def __unicode__(self):
        if self.time:
            return u'%s %s- %s %s' % (self.userset, self.userset.slug,
                                     self.date, self.time)
        else:
            return u'%s %s- %s' % (self.userset, self.userset.slug, self.date)

    def get_datetime(self):
        if self.time:
            return datetime.combine(self.date, self.time)
        else:
            return datetime.combine(self.date, time())
    datetime = property(get_datetime)

    def get_seconds(self):
        td = self.get_datetime() - datetime.now()

        return td.days * 3600 * 24 + td.seconds
    seconds = property(get_seconds)

    def is_expired(self):
        if self.time:
            return datetime.combine(self.date, self.time) < datetime.now()
        else:
            return self.date <= datetime.now().date()
    expired = property(is_expired)

    def get_slug(self):
        return self.userset.slug
    slug = property(get_slug)

    def get_course(self):
        return self.userset.course
    course = property(get_course)
