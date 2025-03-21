# This file is part of the plan timetable generator, see LICENSE for details.

import datetime

from django.conf import settings
from django.core.cache import cache
from django.db import connection, models
from django.template import defaultfilters as filters
from django.utils import dates, translation

from plan.common.managers import (
    CourseManager,
    ExamManager,
    LectureManager,
    SemesterManager,
    SubscriptionManager,
)

# To allow for overriding of the codes idea of now() for tests
now = datetime.datetime.now
today = datetime.date.today

# Setup common alias for translation
_ = translation.gettext_lazy


# TODO(adamcik): Student model isn't really needed once deadlines is removed.
class Student(models.Model):
    id = models.AutoField(primary_key=True)
    slug = models.SlugField(_("Slug"), unique=True)
    # TODO(adamcik): Delete this
    show_deadlines = models.BooleanField(_("Show deadlines"), default=False)

    class Meta:
        verbose_name = _("Student")
        verbose_name_plural = _("Students")

    def __str__(self):
        return self.slug


class Location(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(_("Location"), max_length=100, unique=True)

    class Meta:
        verbose_name = _("Location")
        verbose_name_plural = _("Locations")

    def __str__(self):
        return self.name


class Subscription(models.Model):
    id = models.AutoField(primary_key=True)
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    course = models.ForeignKey("Course", on_delete=models.CASCADE)

    alias = models.CharField(_("Alias"), max_length=50, blank=True)

    added = models.DateTimeField(_("Added"), auto_now_add=True)
    last_modified = models.DateTimeField(_("Modified"), auto_now=True)

    groups = models.ManyToManyField("Group")
    exclude = models.ManyToManyField("Lecture", related_name="excluded_from")

    objects = SubscriptionManager()

    class Meta:
        unique_together = (("student", "course"),)

        verbose_name = _("Subscription")
        verbose_name_plural = _("Subscriptions")

    def __str__(self):
        return f"{self.student} - {self.course}"

    @staticmethod
    def get_groups(year, semester_type, slug):
        tmp = {}

        group_list = (
            Group.objects.filter(
                subscription__student__slug=slug,
                subscription__course__semester__year__exact=year,
                subscription__course__semester__type__exact=semester_type,
            )
            .extra(
                select={
                    "subscription_id": "common_subscription.id",
                    "group_id": "common_group.id",
                }
            )
            .values_list("subscription_id", "group_id")
            .distinct()
            .order_by("code")
        )

        for subscription, group in group_list:
            if subscription not in tmp:
                tmp[subscription] = []
            tmp[subscription].append(group)

        return tmp


# TODO(adamcik): get rid of optional since it can't be imported?
class LectureType(models.Model):
    id = models.AutoField(primary_key=True)
    code = models.CharField(_("Code"), max_length=20, null=True, unique=True)
    name = models.CharField(_("Name"), max_length=100, unique=True)
    optional = models.BooleanField(_("Optional"), default=False)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _("Lecture type")
        verbose_name_plural = _("Lecture types")


# TODO: Consider connecting to a semester(s) to avoid update issues and make imports easier?
# TODO: Track campus things are on as well?
class Room(models.Model):
    id = models.AutoField(primary_key=True)
    code = models.CharField(_("Code"), max_length=100, null=True, unique=True)
    name = models.CharField(_("Name"), max_length=100)
    url = models.TextField(_("URL"), default="")

    last_import = models.DateTimeField(_("Last import time"), auto_now=True)
    last_modified = models.DateTimeField(_("Last modified"), null=True)

    def __str__(self):
        return f"{self.name} ({self.code})"

    class Meta:
        verbose_name = _("Room")
        verbose_name_plural = _("Rooms")
        unique_together = ("code", "name")


# TODO: See if we can handle missing group better than default fallback?
class Group(models.Model):
    DEFAULT = "Other"

    id = models.AutoField(primary_key=True)
    code = models.CharField(_("Code"), max_length=20, unique=True, null=True)
    name = models.CharField(_("Name"), max_length=100, null=True)
    url = models.TextField(_("URL"), default="")

    def __str__(self):
        return self.code

    class Meta:
        verbose_name = _("Group")
        verbose_name_plural = _("Groups")


# TODO(adamcik): link to groups with required field on intermediate. This
# field would indicate if the course is mandidtory for a given group might also
# be an idea to add the year/semester it is expected you take the course?
class Course(models.Model):
    id = models.AutoField(primary_key=True)
    code = models.CharField(_("Code"), max_length=100)
    semester = models.ForeignKey("Semester", on_delete=models.CASCADE)
    locations = models.ManyToManyField(Location)

    name = models.TextField(_("Name"))
    version = models.CharField(_("Version"), max_length=20, null=True)

    url = models.TextField(_("URL"))
    syllabus = models.URLField(_("URL"))
    points = models.DecimalField(_("Points"), decimal_places=2, max_digits=5, null=True)

    last_import = models.DateTimeField(_("Last import time"), auto_now=True)
    last_modified = models.DateTimeField(_("Last modified"), null=True)

    objects = CourseManager()

    class Meta:
        verbose_name = _("Course")
        verbose_name_plural = _("Courses")

        unique_together = [("code", "semester", "version")]

    def __str__(self):
        if self.version:
            name = "-".join([self.code, self.version])
        else:
            name = self.code

        if self.semester:
            return "%-12s - %s" % (name, self.semester)

        return name

    @property
    def short_name(self):
        if self.version:
            return "-".join([self.code, self.version])
        return self.code

    # TODO(adamcik): move limit to setting?
    @staticmethod
    def get_stats(semester=None, limit=None):
        limit = limit or settings.TIMETABLE_TOP_COURSE_COUNT
        if hasattr(semester, "pk"):
            semester_id = semester.pk
        else:
            semester_id = semester

        key = "course-semester-stats-%d-%d" % (semester_id, limit)
        result = cache.get(key)

        if result:
            return result

        slug_count = int(
            Student.objects.filter(subscription__course__semester=semester)
            .distinct()
            .count()
        )
        subscription_count = int(
            Subscription.objects.filter(course__semester=semester).count()
        )
        course_count = int(
            Course.objects.filter(subscription__course__semester=semester)
            .values("name")
            .distinct()
            .count()
        )

        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) as num, c.id, c.code, c.name FROM
                common_subscription u JOIN common_course c ON (c.id = u.course_id)
            WHERE c.semester_id = %s
            GROUP BY c.id, c.code, c.name
            ORDER BY num DESC
            LIMIT %s""",
            [semester_id, limit],
        )

        result = {
            "slug_count": slug_count,
            "course_count": course_count,
            "subscription_count": subscription_count,
            "stats": cursor.fetchall(),
            "limit": limit,
        }
        cache.set(key, result, 300)
        return result

    @staticmethod
    def get_groups(year, semester_type, courses):
        tmp = {}

        group_list = (
            Group.objects.filter(
                lecture__course__in=courses,
                lecture__course__semester__year__exact=year,
                lecture__course__semester__type__exact=semester_type,
            )
            .extra(
                select={
                    "course_id": "common_lecture.course_id",
                    "group_id": "common_group.id",
                }
            )
            .values_list("course_id", "group_id", "code")
            .distinct()
            .order_by("code")
        )

        for course, group, code in group_list:
            if course not in tmp:
                tmp[course] = []
            tmp[course].append((group, code))

        return tmp


class Semester(models.Model):
    SPRING = "spring"
    FALL = "fall"

    SEMESTER_TYPES = (
        (SPRING, _("spring")),
        (FALL, _("fall")),
    )

    SEMESTER_SLUG = (
        (SPRING, translation.pgettext_lazy("slug", "spring")),
        (FALL, translation.pgettext_lazy("slug", "fall")),
    )

    id = models.AutoField(primary_key=True)
    year = models.PositiveSmallIntegerField(_("Year"))
    type = models.CharField(_("Type"), max_length=10, choices=SEMESTER_TYPES)
    active = models.DateField(_("Active"), null=True)

    objects = SemesterManager()

    class Meta:
        verbose_name = _("Semester")
        verbose_name_plural = _("Semesters")

        unique_together = [("year", "type")]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        slug_map = {v: k for k, v in self.SEMESTER_SLUG}

        if self.year:
            self.year = int(self.year)
        if self.type in slug_map:
            self.type = slug_map[self.type]

    def __str__(self):
        return f"{self.get_type_display()} {self.year}"

    @property
    def stale(self) -> bool:
        today = datetime.date.today()
        if self.active is None:
            return today.year - self.year > 2
        return today - self.active > datetime.timedelta(days=365)

    @property
    def slug(self):
        return self.localize(self.type)

    @classmethod
    def localize(cls, semester_type):
        return dict(cls.SEMESTER_SLUG)[semester_type]

    # TODO(adamcik): this is scraper specific...
    @property
    def prefix(self):
        if self.type == self.SPRING:
            return "v%s" % str(self.year)[-2:]
        else:
            return "h%s" % str(self.year)[-2:]


class ExamType(models.Model):
    id = models.AutoField(primary_key=True)
    code = models.CharField(_("Code"), max_length=20, unique=True)
    name = models.CharField(_("Name"), max_length=100, null=True)

    last_import = models.DateTimeField(_("Last import time"), auto_now=True)

    def __str__(self):
        if self.name:
            return self.name
        return self.code

    class Meta:
        verbose_name = _("Exam type")
        verbose_name_plural = _("Exam types")


class Exam(models.Model):
    id = models.AutoField(primary_key=True)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    type = models.ForeignKey(ExamType, null=True, on_delete=models.CASCADE)
    combination = models.CharField(_("Combination"), max_length=50, null=True)

    exam_date = models.DateField(_("Exam date"), null=True)
    exam_time = models.TimeField(_("Exam time"), null=True)

    handout_date = models.DateField(_("Handout date"), null=True)
    handout_time = models.TimeField(_("Handout time"), null=True)

    duration = models.DecimalField(
        _("Duration"),
        null=True,
        max_digits=5,
        decimal_places=2,
        help_text=_("Duration in hours"),
    )
    url = models.TextField(_("URL"), default="")

    # TODO: add link to a location/campus?

    last_import = models.DateTimeField(_("Last import time"), auto_now=True)
    last_modified = models.DateTimeField(_("Last modified"), null=True)

    objects = ExamManager()

    class Meta:
        verbose_name = _("Exam")
        verbose_name_plural = _("Exams")

    def __str__(self):
        return f"{self.course.code} {self.combination} - {self.exam_date}"


class Week(models.Model):
    NUMBER_CHOICES = [(x, x) for x in range(1, 53)]

    id = models.AutoField(primary_key=True)
    lecture = models.ForeignKey(
        "Lecture", related_name="weeks", on_delete=models.CASCADE
    )
    number = models.PositiveIntegerField(_("Week number"), choices=NUMBER_CHOICES)

    class Meta:
        unique_together = [("lecture", "number")]

        verbose_name = _("Lecture week")
        verbose_name_plural = _("Lecture weeks")

    def __str__(self):
        return "%s week %d" % (self.lecture, self.number)


class Lecturer(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(_("Name"), max_length=200, unique=True)
    # TODO: url

    class Meta:
        verbose_name = _("Lecturer")
        verbose_name_plural = _("Lecturers")

    def __str__(self):
        return self.name


class Lecture(models.Model):
    DAYS = [(i, dates.WEEKDAYS[i]) for i in range(5)]

    id = models.AutoField(primary_key=True)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    title = models.TextField(_("Title"), null=True)
    summary = models.TextField(_("Summary"), null=True)
    stream = models.TextField(_("Stream"), null=True)

    day = models.PositiveSmallIntegerField(_("Week day"), choices=DAYS)

    start = models.TimeField(_("Start time"))
    end = models.TimeField(_("End time"))

    rooms = models.ManyToManyField(Room)
    type = models.ForeignKey(LectureType, null=True, on_delete=models.CASCADE)
    groups = models.ManyToManyField(Group)
    lecturers = models.ManyToManyField(Lecturer)

    last_import = models.DateTimeField(_("Last import time"), auto_now=True)
    last_modified = models.DateTimeField(_("Last modified"), null=True)

    objects = LectureManager()

    class Meta:
        verbose_name = _("Lecture")
        verbose_name_plural = _("Lecture")

    def __str__(self):
        return "{} {}-{} on {} for {}".format(
            self.type,
            filters.time(self.start),
            filters.time(self.end),
            self.get_day_display()[:3],
            self.course.code,
        )

    @property
    def short_name(self):
        return "{}-{} on {}".format(
            filters.time(self.start), filters.time(self.end), self.get_day_display()
        )

    @staticmethod
    def get_related(model, lectures, fields=None, use_extra=True):
        tmp = {}

        if not lectures:
            return tmp

        if fields is None:
            fields = ["name"]

        name = model._meta.object_name.lower()

        objects = model.objects.filter(lecture__in=lectures)

        if use_extra:
            objects = objects.extra(
                select={
                    "lecture_id": "common_lecture_%ss.lecture_id" % name,
                }
            )
        object_list = objects.values_list("lecture_id", *fields)

        for obj in object_list:
            lecture = obj[0]

            if lecture not in tmp:
                tmp[lecture] = []

            if len(fields) == 1:
                tmp[lecture].append(obj[1])
            else:
                tmp[lecture].append(dict(map(lambda x, y: (x, y), fields, obj[1:])))

        return tmp


# TODO(adamcik): Delete
class Deadline(models.Model):
    id = models.AutoField(primary_key=True)
    subscription = models.ForeignKey("Subscription", on_delete=models.CASCADE)
    task = models.CharField(_("Task"), max_length=255)
    date = models.DateField(_("Due date"))
    time = models.TimeField(_("Time"), null=True)
    done = models.DateTimeField(_("Done"), null=True)
