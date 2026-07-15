# This file is part of the plan timetable generator, see LICENSE for details.

from django.http import HttpResponse
from django.test import override_settings

from django.conf import settings
from django.core.cache import caches

from plan.common.schedule import Schedule
from plan.common.snapshot import semester_freshness_cache_key
from plan.common.tests import BaseTestCase
from plan.common.utils import (
    ColorMap,
    clear_cache,
    compact_sequence,
    lookup_cached_response,
    store_cached_response,
)


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

    def test_response_cache_headers_do_not_include_the_cache_key(self):
        response = store_cached_response(
            cache_alias="default",
            cache_key="student-123",
            response=HttpResponse(),
            timeout=60,
        )

        self.assertEqual("miss", response.headers["X-Cache"])

        cached = lookup_cached_response(
            cache_alias="default",
            cache_key="student-123",
            headers={},
        )

        self.assertIsNotNone(cached)
        self.assertEqual("hit", cached.headers["X-Cache"])

    def test_clear_cache_deletes_only_user_schedule_entry(self):
        schedule = Schedule(semester=self.semester, student=self.student)
        freshness = schedule.freshness_key()

        dto_key = (
            f"schedule:v2:{self.semester.year}-{self.semester.type}-{self.student.slug}"
        )
        semester_key = semester_freshness_cache_key(self.semester)
        db_key = f"db:schedule:{freshness}"
        resp_key = f"resp:schedule:{freshness}:/"

        caches["default"].set(dto_key, "dto", timeout=60)
        caches["disk"].set(dto_key, "dto", timeout=60)
        caches["default"].set(semester_key, "semester", timeout=60)
        caches["default"].set(db_key, "db", timeout=60)
        caches["default"].set(resp_key, "resp", timeout=60)

        clear_cache(schedule)

        self.assertIsNone(caches["default"].get(dto_key))
        self.assertIsNone(caches["disk"].get(dto_key))
        self.assertEqual("semester", caches["default"].get(semester_key))
        self.assertEqual("db", caches["default"].get(db_key))
        self.assertEqual("resp", caches["default"].get(resp_key))

    @override_settings(
        CACHES={
            "default": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                "LOCATION": "default-utils",
            },
            "disk": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                "LOCATION": "disk-utils",
            },
            "ical": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                "LOCATION": "ical-utils",
            },
        }
    )
    def test_store_cached_response_rejects_unsupported_queued_aliases(self):
        with self.assertRaisesRegex(ValueError, "queued response caching"):
            store_cached_response(
                cache_alias="ical",
                cache_key="key",
                response=HttpResponse("ok"),
                timeout=60,
                queued=True,
            )
