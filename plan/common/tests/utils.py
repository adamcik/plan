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

from django.conf import settings

from plan.common.tests.base import BaseTestCase
from plan.common.utils import ColorMap, compact_sequence

class UtilTestCase(BaseTestCase):
    fixtures = ['test_data.json']

    def test_colormap(self):

        c = ColorMap()
        keys = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 3, 5, 6]
        for k in keys:
            self.assertEquals(c[k], 'color%d' % (k % c.max))

        c = ColorMap(hex=True)
        for k in keys:
            self.assertEquals(c[k], settings.TIMETABLE_COLORS[k % c.max])

        self.assertEquals(c[None], '')

    def test_compact_sequence(self):

        seq = compact_sequence([1, 2, 3, 5, 6, 7, 8, 12, 13, 15, 17, 19])
        self.assertEquals(seq, ['1-3', '5-8', '12-13', '15', '17', '19'])

        seq = compact_sequence([1, 2, 3])
        self.assertEquals(seq, ['1-3'])

        seq = compact_sequence([1, 3])
        self.assertEquals(seq, ['1', '3'])

        seq = compact_sequence([])
        self.assertEquals(seq, [])
