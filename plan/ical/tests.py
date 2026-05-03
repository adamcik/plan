# This file is part of the plan timetable generator, see LICENSE for details.

import datetime

from django.core.cache import caches
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
