# Copyright 2009 Thomas Kongevold Adamcik
# 2009 IME Faculty Norwegian University of Science and Technology

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

from django.test import TestCase
from django.conf import settings

from plan.cache import cache

class NotUsingDummyCache(TestCase):
    def testNotUsingDummyCache(self):
        self.assertEquals(False, 'dummy' in settings.CACHES['default']['BACKEND'])

        self.assertEquals(None, cache.get('test-value'))

        cache.set('test-value', 'foo')

        self.assertEquals('foo', cache.get('test-value'))

        cache.delete('test-value')

        self.assertEquals(None, cache.get('test-value'))
