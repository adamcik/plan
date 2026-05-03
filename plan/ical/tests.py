# This file is part of the plan timetable generator, see LICENSE for details.

import datetime

from django.core.cache import caches
from django.urls import reverse
from django.utils import http as http_utils

from plan.common import tests
from plan.common.models import Semester
from plan.common.schedule import Schedule


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
        self.assertIn("hit", identity_first.headers["X-Cache"])

        br_second = self.client.get(url, HTTP_ACCEPT_ENCODING="br")
        identity_second = self.client.get(url, HTTP_ACCEPT_ENCODING="")
        gzip_first = self.client.get(url, HTTP_ACCEPT_ENCODING="gzip")
        gzip_second = self.client.get(url, HTTP_ACCEPT_ENCODING="gzip")

        self.assertIn("hit", br_second.headers["X-Cache"])
        self.assertIn(":br", br_second.headers["X-Cache"])
        self.assertIn("hit", identity_second.headers["X-Cache"])
        self.assertIn(":identity", identity_second.headers["X-Cache"])
        self.assertIn("hit", gzip_first.headers["X-Cache"])
        self.assertIn(":gzip", gzip_first.headers["X-Cache"])
        self.assertIn("hit", gzip_second.headers["X-Cache"])
        self.assertIn(":gzip", gzip_second.headers["X-Cache"])

    def test_ical_cache_falls_back_to_other_variant_before_regeneration(self):
        url = reverse("schedule-ical", args=[self.schedule])

        identity_first = self.client.get(url, HTTP_ACCEPT_ENCODING="")
        self.assertEqual(identity_first.status_code, 200)
        self.assertIn("miss", identity_first.headers["X-Cache"])
        self.assertIn(":identity", identity_first.headers["X-Cache"])

        br_after_identity = self.client.get(url, HTTP_ACCEPT_ENCODING="br")
        self.assertEqual(br_after_identity.status_code, 200)
        self.assertIn("hit", br_after_identity.headers["X-Cache"])
        self.assertIn(":br", br_after_identity.headers["X-Cache"])

        gzip_after_identity = self.client.get(url, HTTP_ACCEPT_ENCODING="gzip")
        self.assertEqual(gzip_after_identity.status_code, 200)
        self.assertIn("hit", gzip_after_identity.headers["X-Cache"])
        self.assertIn(":gzip", gzip_after_identity.headers["X-Cache"])

    def test_ical_cache_control_uses_stale_only_for_http_window(self):
        current_year = datetime.date.today().year
        semester = Semester.objects.create(year=current_year, type=Semester.SPRING)
        current_schedule = Schedule(semester=semester, student=self.student)
        current_url = reverse("schedule-ical", args=[current_schedule])
        stale_url = reverse("schedule-ical", args=[self.schedule])

        current = self.client.get(f"{current_url}?no-cache=1", HTTP_ACCEPT_ENCODING="")
        self.assertEqual(current.status_code, 200)

        stale = self.client.get(f"{stale_url}?no-cache=1", HTTP_ACCEPT_ENCODING="")
        self.assertEqual(stale.status_code, 200)

        current_max_age = int(current.headers["Cache-Control"].split("=")[1])
        stale_max_age = int(stale.headers["Cache-Control"].split("=")[1])

        self.assertGreaterEqual(current_max_age, 3600)
        self.assertLessEqual(current_max_age, 3960)
        self.assertGreaterEqual(stale_max_age, 7776000)
        self.assertLessEqual(stale_max_age, 8553600)
        self.assertGreater(stale_max_age, current_max_age)
