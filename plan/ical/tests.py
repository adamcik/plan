# This file is part of the plan timetable generator, see LICENSE for details.

import datetime

from django.core.cache import caches
from django.test import override_settings
from django.urls import reverse
from django.utils import http as http_utils

from plan.common import tests


class EmptyViewTestCase(tests.BaseTestCase):
    def setUp(self):
        super().setUp()
        caches["default"].clear()
        caches["ical"].clear()

    def test_ical(self):
        """This covers the semester not existing."""

        url = reverse("schedule-ical", args=[self.schedule])
        self.assertEqual(self.client.get(url).status_code, 404)

        for arg in ("exams", "lectures"):
            url = reverse("schedule-ical-type", args=[self.schedule, arg])
            self.assertEqual(self.client.get(url).status_code, 404)

        url = reverse("schedule-ical-type", args=[self.schedule, "foo"])
        self.assertEqual(self.client.get(url).status_code, 404)


class ViewTestCase(tests.BaseTestCase):
    fixtures = ["test_data.json", "test_user.json"]

    def setUp(self):
        super().setUp()
        caches["default"].clear()
        caches["ical"].clear()

    def test_ical(self):
        url = reverse("schedule-ical", args=[self.schedule])
        self.assertEqual(self.client.get(url).status_code, 200)

        for arg in ("exams", "lectures"):
            url = reverse("schedule-ical-type", args=[self.schedule, arg])
            self.assertEqual(self.client.get(url).status_code, 200)

        url = reverse("schedule-ical-type", args=[self.schedule, "foo"])
        self.assertEqual(self.client.get(url).status_code, 400)

        # TODO: Test with slug that does not exist?

    def test_ical_not_modified_returns_304_with_cache_headers(self):
        url = reverse("schedule-ical", args=[self.schedule])
        first = self.client.get(url)

        self.assertEqual(first.status_code, 200)
        self.assertIn("Last-Modified", first.headers)

        second = self.client.get(
            url,
            HTTP_IF_MODIFIED_SINCE=first.headers["Last-Modified"],
        )

        self.assertEqual(second.status_code, 304)
        self.assertEqual(second.content, b"")
        self.assertIn("Last-Modified", second.headers)
        self.assertIn("Cache-Control", second.headers)
        self.assertIn("Expires", second.headers)

    def test_ical_uses_last_modified_for_dtstamp(self):
        url = reverse("schedule-ical", args=[self.schedule])

        response = self.client.get(f"{url}?no-cache=1")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Last-Modified", response.headers)

        timestamp = http_utils.parse_http_date(response.headers["Last-Modified"])
        dtstamp = datetime.datetime.fromtimestamp(
            timestamp,
            tz=datetime.timezone.utc,
        ).strftime("%Y%m%dT%H%M%SZ")

        body = response.content.decode()
        self.assertIn(f"DTSTAMP:{dtstamp}", body)

    def test_ical_cache_uses_encoding_variants(self):
        url = reverse("schedule-ical", args=[self.schedule])

        br_first = self.client.get(url, HTTP_ACCEPT_ENCODING="br")
        identity_first = self.client.get(url, HTTP_ACCEPT_ENCODING="")

        self.assertEqual(br_first.status_code, 200)
        self.assertEqual(identity_first.status_code, 200)
        self.assertIn("X-Cache", br_first.headers)
        self.assertIn("X-Cache", identity_first.headers)
        self.assertIn(":br", br_first.headers["X-Cache"])
        self.assertIn(":identity", identity_first.headers["X-Cache"])
        self.assertIn("miss", br_first.headers["X-Cache"])
        self.assertIn("miss", identity_first.headers["X-Cache"])

        br_second = self.client.get(url, HTTP_ACCEPT_ENCODING="br")
        identity_second = self.client.get(url, HTTP_ACCEPT_ENCODING="")
        gzip_first = self.client.get(url, HTTP_ACCEPT_ENCODING="gzip")
        gzip_second = self.client.get(url, HTTP_ACCEPT_ENCODING="gzip")

        self.assertIn("hit", br_second.headers["X-Cache"])
        self.assertIn(":br", br_second.headers["X-Cache"])
        self.assertIn("hit", identity_second.headers["X-Cache"])
        self.assertIn(":identity", identity_second.headers["X-Cache"])
        self.assertIn("miss", gzip_first.headers["X-Cache"])
        self.assertIn(":gzip", gzip_first.headers["X-Cache"])
        self.assertIn("hit", gzip_second.headers["X-Cache"])
        self.assertIn(":gzip", gzip_second.headers["X-Cache"])

    @override_settings(TIMETABLE_ICAL_CACHE_DURATION=datetime.timedelta(microseconds=1))
    def test_ical_stale_semester_cache_does_not_expire_with_short_global_ttl(self):
        self.set_now_to(2026, 1, 1)
        caches["ical"].clear()

        url = reverse("schedule-ical", args=[self.schedule])
        first = self.client.get(url, HTTP_ACCEPT_ENCODING="")

        self.assertEqual(first.status_code, 200)
        self.assertIn("miss", first.headers["X-Cache"])

        second = self.client.get(url, HTTP_ACCEPT_ENCODING="")

        self.assertEqual(second.status_code, 200)
        self.assertIn("hit", second.headers["X-Cache"])
