from datetime import datetime

from django.core.urlresolvers import reverse
from django.test import TestCase

from plan.common.models import Semester
from plan.common.cache import get_realm, clear_cache, cache

class BaseTestCase(TestCase):
    def setUp(self):
        from plan.common import models, views
        models.now = lambda: datetime(2009, 1, 1)
        views.now = lambda: datetime(2009, 1, 1)

        self.semester = Semester.current()

        self.realm = get_realm(self.semester, 'adamcik')
        self.default_args = [
                self.semester.year,
                self.semester.get_url_type_display(),
                'adamcik'
            ]

    def url(self, name, *args):
        if args:
            return reverse(name, args=args)
        else:
            return reverse(name, args=self.default_args)

    def url_basic(self, name):
        return reverse(name)

    def clear(self, ):
        clear_cache(self.semester, 'adamcik')

    def get(self, key):
        return cache.get(key, realm=self.realm)
