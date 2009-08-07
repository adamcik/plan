# encoding: utf-8

# Copyright 2008, 2009 Thomas Kongevold Adamcik

# This file is part of Plan.
#
# Plan is free software: you can redistribute it and/or modify
# it under the terms of the Affero GNU General Public License as 
# published by the Free Software Foundation, either version 3 of
# the License, or (at your option) any later version.
#
# Plan is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# Affero GNU General Public License for more details.
#
# You should have received a copy of the Affero GNU General Public
# License along with Plan.  If not, see <http://www.gnu.org/licenses/>.

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
                self.semester.type,
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
