# This file is part of the plan timetable generator, see LICENSE for details.

from django.conf import settings

from plan.common.tests import BaseTestCase
from plan.common.utils import ColorMap, compact_sequence


class UtilTestCase(BaseTestCase):
    fixtures = ["test_data.json"]

    def test_colormap(self):

        c = ColorMap()
        keys = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 3, 5, 6]
        for k in keys:
            self.assertEqual(c[k], "color%d" % (k % c.max))

        c = ColorMap(hex=True)
        for k in keys:
            self.assertEqual(c[k], settings.TIMETABLE_COLORS[k % c.max])

        self.assertEqual(c[None], "")

    def test_compact_sequence(self):

        seq = compact_sequence([1, 2, 3, 5, 6, 7, 8, 12, 13, 15, 17, 19])
        self.assertEqual(seq, ["1-3", "5-8", "12-13", "15", "17", "19"])

        seq = compact_sequence([1, 2, 3])
        self.assertEqual(seq, ["1-3"])

        seq = compact_sequence([1, 3])
        self.assertEqual(seq, ["1", "3"])

        seq = compact_sequence([])
        self.assertEqual(seq, [])
