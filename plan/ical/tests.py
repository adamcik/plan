# This file is part of the plan timetable generator, see LICENSE for details.

import datetime
import gzip

import brotli
from django.core.cache import caches
from django.http import HttpResponse
from django.test import RequestFactory
from django.test import override_settings
from django.urls import reverse
from django.utils import http as http_utils

from plan.common import tests, utils
from plan.common.converters import ScheduleConverter
from plan.common.models import Semester
from plan.common.schedule import Schedule
from plan.ical import queue
from plan.ical import views


class EmptyViewTestCase(tests.BaseTestCase):
    def setUp(self):
        super().setUp()
        queue.flush_for_tests()
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
        queue.flush_for_tests()
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
        queue.flush_for_tests()
        identity_first = self.client.get(url, HTTP_ACCEPT_ENCODING="")
        queue.flush_for_tests()

        self.assertEqual(br_first.status_code, 200)
        self.assertEqual(identity_first.status_code, 200)
        self.assertIn("X-Cache", br_first.headers)
        self.assertIn("X-Cache", identity_first.headers)
        self.assertIn(":br", br_first.headers["X-Cache"])
        self.assertIn(":identity", identity_first.headers["X-Cache"])
        self.assertIn("miss", br_first.headers["X-Cache"])
        self.assertIn("hit", identity_first.headers["X-Cache"])

        br_second = self.client.get(url, HTTP_ACCEPT_ENCODING="br")
        queue.flush_for_tests()
        identity_second = self.client.get(url, HTTP_ACCEPT_ENCODING="")
        queue.flush_for_tests()
        gzip_first = self.client.get(url, HTTP_ACCEPT_ENCODING="gzip")
        queue.flush_for_tests()
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
        queue.flush_for_tests()
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
        self.assertIn("upgraded=", response.headers["X-Cache"])
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
        self.assertIn("upgraded=", response.headers["X-Cache"])
        self.assertIn(f"key={legacy_v1_key}", response.headers["X-Cache"])
        self.assertEqual(response.content, b"legacy-v1")

    def test_ical_reads_legacy_key_with_trailing_slash_path(self):
        url = reverse("schedule-ical", args=[self.schedule])
        resolved = ScheduleConverter().to_python(
            f"{self.semester.year}/{self.semester.slug}/{self.student.slug}"
        )
        legacy_v2_key = ":".join(
            (
                "resp",
                "v2",
                "schedule-ical",
                url,
                str(resolved.last_modified),
                "identity",
            )
        )
        caches["ical"].set(
            legacy_v2_key,
            HttpResponse(
                "legacy-trailing-slash", content_type="text/calendar; charset=utf-8"
            ),
        )

        response = self.client.get(url, HTTP_ACCEPT_ENCODING="")

        self.assertEqual(response.status_code, 200)
        self.assertIn("upgraded=", response.headers["X-Cache"])
        self.assertIn(f"key={legacy_v2_key}", response.headers["X-Cache"])
        self.assertEqual(response.content, b"legacy-trailing-slash")

    def test_ical_type_reads_legacy_key_from_fallback_route_name(self):
        url = reverse("schedule-ical-type", args=[self.schedule, "lectures"])
        no_slash = url.rstrip("/")
        resolved = ScheduleConverter().to_python(
            f"{self.semester.year}/{self.semester.slug}/{self.student.slug}"
        )
        legacy_v2_key = ":".join(
            (
                "resp",
                "v2",
                "schedule-ical-type-fallback",
                no_slash,
                str(resolved.last_modified),
                "identity",
            )
        )
        caches["ical"].set(
            legacy_v2_key,
            HttpResponse(
                "legacy-fallback-route", content_type="text/calendar; charset=utf-8"
            ),
        )

        response = self.client.get(no_slash, HTTP_ACCEPT_ENCODING="")

        self.assertEqual(response.status_code, 200)
        self.assertIn("upgraded=", response.headers["X-Cache"])
        self.assertIn(f"key={legacy_v2_key}", response.headers["X-Cache"])
        self.assertEqual(response.content, b"legacy-fallback-route")

    def test_ical_legacy_cache_fallback_matrix(self):
        resolved = ScheduleConverter().to_python(
            f"{self.semester.year}/{self.semester.slug}/{self.student.slug}"
        )

        cases = [
            {
                "name": "base-v1-no-slash-identity",
                "url_name": "schedule-ical",
                "url_args": [self.schedule],
                "legacy_route": "schedule-ical",
                "legacy_path_variant": "no-slash",
                "legacy_kind": "v1",
                "legacy_encoding": "identity",
                "request_encoding": "",
            },
            {
                "name": "base-v2-with-slash-gzip",
                "url_name": "schedule-ical",
                "url_args": [self.schedule],
                "legacy_route": "schedule-ical",
                "legacy_path_variant": "with-slash",
                "legacy_kind": "v2",
                "legacy_encoding": "gzip",
                "request_encoding": "gzip",
            },
            {
                "name": "type-v2-fallback-route-identity",
                "url_name": "schedule-ical-type",
                "url_args": [self.schedule, "lectures"],
                "legacy_route": "schedule-ical-type-fallback",
                "legacy_path_variant": "no-slash",
                "legacy_kind": "v2",
                "legacy_encoding": "identity",
                "request_encoding": "",
            },
            {
                "name": "type-v2-canonical-route-br",
                "url_name": "schedule-ical-type",
                "url_args": [self.schedule, "lectures"],
                "legacy_route": "schedule-ical-type",
                "legacy_path_variant": "with-slash",
                "legacy_kind": "v2",
                "legacy_encoding": "br",
                "request_encoding": "br",
            },
        ]

        for case in cases:
            queue.flush_for_tests()
            caches["ical"].clear()
            url = reverse(case["url_name"], args=case["url_args"])
            no_slash = url.rstrip("/")
            with_slash = f"{no_slash}/"
            legacy_path = no_slash
            if case["legacy_path_variant"] == "with-slash":
                legacy_path = with_slash

            expected_content = f"legacy-matrix:{case['name']}".encode()
            payload = expected_content
            headers = {"Content-Type": "text/calendar; charset=utf-8"}
            if case["legacy_encoding"] == "gzip":
                payload = gzip.compress(expected_content, compresslevel=6, mtime=0)
                headers["Content-Encoding"] = "gzip"
            elif case["legacy_encoding"] == "br":
                payload = brotli.compress(expected_content, brotli.MODE_TEXT)
                headers["Content-Encoding"] = "br"

            response_to_store = HttpResponse(payload, headers=headers)

            if case["legacy_kind"] == "v2":
                legacy_key = ":".join(
                    (
                        "resp",
                        "v2",
                        case["legacy_route"],
                        legacy_path,
                        str(resolved.last_modified),
                        case["legacy_encoding"],
                    )
                )
            else:
                legacy_key = ":".join(
                    (
                        "resp",
                        case["legacy_route"],
                        legacy_path,
                        str(resolved.last_modified),
                    )
                )

            caches["ical"].set(legacy_key, response_to_store)

            response = self.client.get(
                url, HTTP_ACCEPT_ENCODING=case["request_encoding"]
            )

            self.assertEqual(response.status_code, 200, case["name"])
            self.assertIn("upgraded=", response.headers["X-Cache"], case["name"])
            self.assertIn(
                f"key={legacy_key}", response.headers["X-Cache"], case["name"]
            )
            response_content = response.content
            content_encoding = response.headers.get("Content-Encoding")
            if content_encoding == "gzip":
                response_content = gzip.decompress(response_content)
            elif content_encoding == "br":
                response_content = brotli.decompress(response_content)
            self.assertEqual(response_content, expected_content, case["name"])

    def test_legacy_v2_does_not_fallback_across_encodings(self):
        caches["ical"].clear()
        url = reverse("schedule-ical", args=[self.schedule])
        resolved = ScheduleConverter().to_python(
            f"{self.semester.year}/{self.semester.slug}/{self.student.slug}"
        )
        legacy_v2_br_key = ":".join(
            (
                "resp",
                "v2",
                "schedule-ical",
                url,
                str(resolved.last_modified),
                "br",
            )
        )
        marker = b"legacy-v2-br-only"
        caches["ical"].set(
            legacy_v2_br_key,
            HttpResponse(
                brotli.compress(marker, brotli.MODE_TEXT),
                headers={
                    "Content-Type": "text/calendar; charset=utf-8",
                    "Content-Encoding": "br",
                },
            ),
        )

        response = self.client.get(url, HTTP_ACCEPT_ENCODING="gzip")

        self.assertEqual(response.status_code, 200)
        self.assertIn("miss", response.headers["X-Cache"])
        self.assertNotIn("upgraded=", response.headers["X-Cache"])

    def test_legacy_upgrade_populates_current_key_for_next_hit(self):
        caches["ical"].clear()
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

        first = self.client.get(url, HTTP_ACCEPT_ENCODING="")
        queue.flush_for_tests()
        second = self.client.get(url, HTTP_ACCEPT_ENCODING="")

        self.assertEqual(first.status_code, 200)
        self.assertIn("upgraded=", first.headers["X-Cache"])
        self.assertEqual(second.status_code, 200)
        self.assertIn("hit; key=", second.headers["X-Cache"])
        self.assertNotIn("upgraded=", second.headers["X-Cache"])
        self.assertNotIn(f"key={legacy_v1_key}", second.headers["X-Cache"])

    def test_ical_cache_key_is_same_for_type_with_and_without_trailing_slash(self):
        url = reverse("schedule-ical-type", args=[self.schedule, "lectures"])
        no_slash = url.rstrip("/")
        with_slash = f"{no_slash}/"

        first = self.client.get(no_slash, HTTP_ACCEPT_ENCODING="")
        queue.flush_for_tests()
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


class CacheKeyHelpersTestCase(tests.BaseTestCase):
    def test_legacy_paths_are_unique_and_stable(self):
        factory = RequestFactory()

        no_slash = factory.get("/a/b")
        with_slash = factory.get("/a/b/")

        self.assertEqual(views._legacy_paths(no_slash), ["/a/b", "/a/b/"])
        self.assertEqual(views._legacy_paths(with_slash), ["/a/b", "/a/b/"])
