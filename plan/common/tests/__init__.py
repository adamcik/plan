# This file is part of the plan timetable generator, see LICENSE for details.

import datetime
import copy

from django.conf import settings
from django.core.cache import caches
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse

from plan.common.models import Semester, Student
from plan.common.schedule import Schedule


# TODO(adamcik): switch to proper mock lib.
class BaseTestCase(TestCase):
    def setUp(self):
        caches["default"].clear()
        caches["disk"].clear()

        self.set_now_to(2009, 1, 1)

        self.semester = Semester(year=2009, type="spring")
        self.student = Student(slug="adamcik")
        self.schedule = Schedule(semester=self.semester, student=self.student)
        self.next_schedule = Schedule(
            semester=Semester(year=2009, type=Semester.FALL),
            student=self.student,
        )

        self.default_args = [2009, "spring", "adamcik"]

    def set_now_to(self, year, month, day):
        from plan.common import managers, models, views

        dt = datetime.datetime(year, month, day)

        for cls in models, views, managers:
            cls.now = lambda: dt
            cls.today = lambda: dt.date()

    def url(self, name, *args):
        if args:
            return reverse(name, args=args)
        else:
            return reverse(name, args=self.default_args)

    def url_basic(self, name):
        return reverse(name)


class StrictTemplateVariable:
    def __contains__(self, item):
        return item == "%s"

    def __mod__(self, missing):
        raise RuntimeError(f"Missing template variable or attribute: {missing}")

    def __str__(self):
        raise RuntimeError("Missing template variable or attribute")


def strict_template_variables():
    templates = copy.deepcopy(settings.TEMPLATES)
    for backend in templates:
        if backend.get("BACKEND") != "django.template.backends.django.DjangoTemplates":
            continue
        options = backend.setdefault("OPTIONS", {})
        options["string_if_invalid"] = StrictTemplateVariable()
    return override_settings(TEMPLATES=templates)
