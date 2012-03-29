# This file is part of the plan timetable generator, see LICENSE for details.

from datetime import datetime

from django.core.urlresolvers import reverse
from django.test import TestCase

from plan.common.models import Semester


# TODO(adamcik): switch to proper mock lib.
class BaseTestCase(TestCase):
    def setUp(self):
        self.set_now_to(2009, 1, 1)

        self.semester = Semester.current()
        self.default_args = [
                self.semester.year,
                self.semester.type,
                'adamcik'
            ]

    def set_now_to(self, year, month, day):
        from plan.common import models, views
        models.now = lambda: datetime(year, month, day)
        views.now = lambda: datetime(year, month, day)

    def url(self, name, *args):
        if args:
            return reverse(name, args=args)
        else:
            return reverse(name, args=self.default_args)

    def url_basic(self, name):
        return reverse(name)
