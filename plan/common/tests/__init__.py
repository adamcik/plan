# This file is part of the plan timetable generator, see LICENSE for details.

import datetime

from django.test import TestCase
from django.urls import reverse

from plan.common.models import Semester
from plan.common.schedule import Schedule


# TODO(adamcik): switch to proper mock lib.
class BaseTestCase(TestCase):
    def setUp(self):
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
