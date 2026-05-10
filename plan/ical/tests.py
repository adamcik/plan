# This file is part of the plan timetable generator, see LICENSE for details.

import datetime

from django.core.cache import caches
from django.http import HttpResponse
from django.test import override_settings
from django.urls import reverse
from django.utils import http as http_utils

from plan.common import tests, utils
from plan.common.converters import ScheduleConverter
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
            no_slash = url.rstrip("/")
            with_slash = f"{no_slash}/"
            self.assertEqual(self.client.get(no_slash).status_code, 404)
            self.assertEqual(self.client.get(with_slash).status_code, 404)

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
            no_slash = url.rstrip("/")
            with_slash = f"{no_slash}/"
            self.assertEqual(self.client.get(no_slash).status_code, 200)
            self.assertEqual(self.client.get(with_slash).status_code, 200)

        url = reverse("schedule-ical-type", args=[self.schedule, "foo"])
        no_slash = url.rstrip("/")
        with_slash = f"{no_slash}/"
        self.assertEqual(self.client.get(no_slash).status_code, 400)
        self.assertEqual(self.client.get(with_slash).status_code, 400)

        # TODO: Test with slug that does not exist?

    @override_settings(TIMETABLE_ENABLE_IF_MODIFIED_SINCE=True)
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

    def test_ical_get_includes_etag_and_last_modified(self):
        url = reverse("schedule-ical", args=[self.schedule])

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertIn("ETag", response.headers)
        self.assertIn("Last-Modified", response.headers)

    def test_ical_if_none_match_matching_returns_304_with_no_body(self):
        url = reverse("schedule-ical", args=[self.schedule])
        first = self.client.get(url)

        second = self.client.get(
            f"{url}?no-cache=1",
            HTTP_IF_NONE_MATCH=first.headers["ETag"],
        )

        self.assertEqual(second.status_code, 304)
        self.assertEqual(second.content, b"")
        self.assertEqual(second.headers["ETag"], first.headers["ETag"])
        self.assertIn("Last-Modified", second.headers)
        self.assertIn("Cache-Control", second.headers)
        self.assertNotIn("X-Cache", second.headers)

    def test_ical_if_none_match_non_matching_returns_200(self):
        url = reverse("schedule-ical", args=[self.schedule])

        response = self.client.get(url, HTTP_IF_NONE_MATCH='"not-the-tag"')

        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.headers["ETag"], '"not-the-tag"')

    def test_ical_if_none_match_multiple_values_returns_304_on_match(self):
        url = reverse("schedule-ical", args=[self.schedule])
        first = self.client.get(url)

        response = self.client.get(
            url,
            HTTP_IF_NONE_MATCH=f'"foo", {first.headers["ETag"]}, "bar"',
        )

        self.assertEqual(response.status_code, 304)
        self.assertEqual(response.content, b"")

    def test_ical_if_none_match_wildcard_returns_304(self):
        url = reverse("schedule-ical", args=[self.schedule])

        response = self.client.get(url, HTTP_IF_NONE_MATCH="*")

        self.assertEqual(response.status_code, 304)
        self.assertEqual(response.content, b"")

    def test_if_none_match_takes_precedence_over_if_modified_since(self):
        url = reverse("schedule-ical", args=[self.schedule])
        first = self.client.get(url)

        response = self.client.get(
            url,
            HTTP_IF_NONE_MATCH='"does-not-match"',
            HTTP_IF_MODIFIED_SINCE=first.headers["Last-Modified"],
        )

        self.assertEqual(response.status_code, 200)

    def test_ical_head_matches_get_status_and_headers_with_no_body(self):
        url = reverse("schedule-ical", args=[self.schedule])
        get_response = self.client.get(url)

        head_response = self.client.head(url)

        self.assertEqual(head_response.status_code, get_response.status_code)
        self.assertEqual(head_response.headers["ETag"], get_response.headers["ETag"])
        self.assertEqual(
            head_response.headers["Last-Modified"],
            get_response.headers["Last-Modified"],
        )
        self.assertEqual(head_response.content, b"")

        conditional_head = self.client.head(
            url, HTTP_IF_NONE_MATCH=get_response.headers["ETag"]
        )

        self.assertEqual(conditional_head.status_code, 304)
        self.assertEqual(conditional_head.content, b"")
        self.assertEqual(conditional_head.headers["ETag"], get_response.headers["ETag"])

    def test_ical_etag_changes_when_cache_key_changes(self):
        url = reverse("schedule-ical", args=[self.schedule])

        identity = self.client.get(url, HTTP_ACCEPT_ENCODING="")
        gzip = self.client.get(url, HTTP_ACCEPT_ENCODING="gzip")

        self.assertEqual(identity.status_code, 200)
        self.assertEqual(gzip.status_code, 200)
        self.assertNotEqual(identity.headers["ETag"], gzip.headers["ETag"])

    def test_ical_etag_is_hashed_not_raw(self):
        url = reverse("schedule-ical", args=[self.schedule])
        resolved = ScheduleConverter().to_python(
            f"{self.semester.year}/{self.semester.slug}/{self.student.slug}"
        )

        response = self.client.get(url, HTTP_ACCEPT_ENCODING="")

        etag = response.headers["ETag"]
        key = utils.response_cache_key(
            "schedule-ical",
            resolved.freshness_key(),
            url.rstrip("/"),
            "identity",
        )
        self.assertTrue(etag.startswith('"') and etag.endswith('"'))
        self.assertEqual(len(etag), 66)
        self.assertEqual(etag, utils.etag_for_key(key))

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

    def test_ical_reads_and_migrates_legacy_v2_cache_key(self):
        url = reverse("schedule-ical", args=[self.schedule])
        path = url.rstrip("/")
        resolved = ScheduleConverter().to_python(
            f"{self.semester.year}/{self.semester.slug}/{self.student.slug}"
        )
        legacy_v2_key = ":".join(
            (
                "resp",
                "v2",
                "schedule-ical",
                path,
                str(resolved.last_modified),
                "identity",
            )
        )
        caches["ical"].set(
            legacy_v2_key,
            HttpResponse("legacy-v2", content_type="text/calendar; charset=utf-8"),
        )

        response = self.client.get(url, HTTP_ACCEPT_ENCODING="")

        self.assertEqual(response.status_code, 200)
        self.assertIn("legacy=1", response.headers["X-Cache"])
        self.assertIn(f"key={legacy_v2_key}", response.headers["X-Cache"])
        self.assertEqual(response.content, b"legacy-v2")

    def test_ical_reads_and_migrates_legacy_v1_cache_key(self):
        url = reverse("schedule-ical", args=[self.schedule])
        path = url.rstrip("/")
        resolved = ScheduleConverter().to_python(
            f"{self.semester.year}/{self.semester.slug}/{self.student.slug}"
        )
        legacy_v1_key = ":".join(
            (
                "resp",
                "schedule-ical",
                path,
                str(resolved.last_modified),
            )
        )
        caches["ical"].set(
            legacy_v1_key,
            HttpResponse("legacy-v1", content_type="text/calendar; charset=utf-8"),
        )

        response = self.client.get(url, HTTP_ACCEPT_ENCODING="")

        self.assertEqual(response.status_code, 200)
        self.assertIn("legacy=1", response.headers["X-Cache"])
        self.assertIn(f"key={legacy_v1_key}", response.headers["X-Cache"])
        self.assertEqual(response.content, b"legacy-v1")

    def test_ical_cache_key_is_same_for_type_with_and_without_trailing_slash(self):
        url = reverse("schedule-ical-type", args=[self.schedule, "lectures"])
        no_slash = url.rstrip("/")
        with_slash = f"{no_slash}/"

        first = self.client.get(no_slash, HTTP_ACCEPT_ENCODING="")
        second = self.client.get(with_slash, HTTP_ACCEPT_ENCODING="")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertIn("miss", first.headers["X-Cache"])
        self.assertIn("hit", second.headers["X-Cache"])

        first_key = first.headers["X-Cache"].split("key=", 1)[1]
        second_key = second.headers["X-Cache"].split("key=", 1)[1]

        self.assertEqual(first_key, second_key)

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
