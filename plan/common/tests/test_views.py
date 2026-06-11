# This file is part of the plan timetable generator, see LICENSE for details.

import datetime
import re
import subprocess
import tempfile
from pathlib import Path

from django.core.cache import cache, caches
from django.test import override_settings
from django.urls import reverse as django_reverse
from django.utils import timezone
from django.utils.datastructures import MultiValueDict

from plan.common import utils
from plan.common.models import (
    Group,
    Lecture,
    Schedule,
    Semester,
    Student,
    Subscription,
)
from plan.common.snapshot import schedule_snapshot_cache_key
from plan.common.tests import BaseTestCase, strict_template_variables

FIXTURE_LECTURE_ID = 12


class EmptyViewTestCase(BaseTestCase):
    def test_index(self):
        response = self.client.get(self.url_basic("frontpage"))

        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")

    def test_shortcut(self):
        response = self.client.get(self.url("shortcut", "adamcik"))

        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")

    def test_robots_txt(self):
        response = self.client.get("/robots.txt")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "User-agent: *")
        self.assertContains(response, "Disallow: /*/*/*/")
        self.assertContains(response, "Disallow: /*/*/*/*")

    def test_favicon(self):
        response = self.client.get("/favicon.ico")

        self.assertEqual(response.status_code, 301)
        self.assertTrue(response["Location"].endswith("/static/favicon.png"))


class ViewTestCase(BaseTestCase):
    fixtures = ["test_data.json", "test_user.json", "test_lecture_events.json"]

    def reverse(self, view_name, *extra_args):
        return django_reverse(
            view_name,
            args=[self.semester, self.student.slug, *extra_args],
        )

    def assert_valid_html5(self, pages):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            for filename, response in pages.items():
                self.assertEqual(
                    response.status_code,
                    200,
                    msg=f"expected 200 for {filename}, got {response.status_code}",
                )
                (root / filename).write_bytes(response.content)

            result = subprocess.run(
                ["html5validator", "--root", tmpdir, "--match", "*.html"],
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(
            result.returncode,
            0,
            msg=f"html5validator failed:\n{result.stdout}{result.stderr}",
        )

    # FIXME check what happens when we do GET against change functions
    # FIXME test adding course that does not exist for a given semester

    def test_index(self):
        response = self.client.get(django_reverse("frontpage"))
        url = django_reverse("semester", args=[self.semester])
        self.assertRedirects(response, url)

    def test_shortcut(self):
        response = self.client.get(self.url("shortcut", "adamcik"))
        url = self.reverse("schedule-week", 1)
        self.assertRedirects(response, url)

        # TODO: Check with other times.

    def test_redirect_room_missing_returns_404(self):
        response = self.client.get(django_reverse("redirect_room", args=[999999]))

        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")

    def test_redirect_missing_returns_404_for_all_types(self):
        for name in (
            "redirect_room",
            "redirect_course",
            "redirect_syllabus",
            "redirect_stream",
        ):
            response = self.client.get(django_reverse(name, args=[999999]))

            self.assertEqual(response.status_code, 404)
            self.assertTemplateUsed(response, "404.html")

    def test_schedule_current(self):
        url = self.reverse("schedule-current")
        response = self.client.get(url)

        self.assertRedirects(response, self.reverse("schedule-week", 1))

        response = self.client.get(
            django_reverse(
                "schedule-current",
                args=[self.next_schedule.semester, self.next_schedule.student.slug],
            )
        )
        self.assertRedirects(
            response,
            django_reverse(
                "schedule",
                args=[self.next_schedule.semester, self.next_schedule.student.slug],
            ),
        )

    def test_getting_started_post_redirects_to_current_schedule(self):
        response = self.client.post(
            django_reverse("semester", args=[self.semester]),
            {"slug": self.student.slug},
        )

        self.assertRedirects(response, self.reverse("schedule-week", 1))

    def test_unknown_semester_name_returns_404(self):
        response = self.client.get("/2009/winter/")

        self.assertEqual(response.status_code, 404)

    def test_semester_alias_redirects_to_canonical_slug(self):
        for alias in ("autum", "autmn", "autumn"):
            with self.subTest(alias=alias):
                response = self.client.get(f"/2026/{alias}/")

                self.assertRedirects(
                    response,
                    "/2026/fall/",
                    status_code=301,
                    fetch_redirect_response=False,
                )

    def test_schedule(self):
        # FIXME add group help testing
        # FIXME courses without lectures
        # FIXME test next semester message
        # FIXME test group-help message

        for url in [
            self.reverse("schedule"),
            self.reverse("schedule-advanced"),
            self.reverse("schedule-week", 1),
            self.reverse("schedule-week", 2),
            self.reverse("schedule"),
        ]:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertTemplateUsed(response, "schedule.html")

    def test_schedule_renders_lecture_and_course_classes_and_room_links(self):
        semester = Semester.objects.get(year=2009, type=Semester.SPRING)
        student = Student.objects.get(slug="adamcik")

        response = self.client.get(self.reverse("schedule"))
        self.assertEqual(response.status_code, 200)

        lectures = Lecture.objects.get_lectures_data(semester.id, student.id)
        lecture = next(
            (l for l in lectures if l.lecture_id == FIXTURE_LECTURE_ID),
            None,
        )
        self.assertIsNotNone(lecture)

        self.assertContains(response, f"lecture-{lecture.lecture_id}")
        self.assertContains(response, f"course-{lecture.course_id}")

    @strict_template_variables()
    def test_schedule_renders_without_missing_template_variables(self):
        response = self.client.get(self.reverse("schedule"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "schedule.html")

    @strict_template_variables()
    def test_schedule_advanced_renders_without_missing_template_variables(self):
        response = self.client.get(self.reverse("schedule-advanced"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "schedule.html")

    def test_schedule_sets_robots_header(self):
        response = self.client.get(self.reverse("schedule"))

        self.assertEqual(
            response.headers["X-Robots-Tag"],
            "noindex, nofollow, noarchive",
        )

    def test_schedule_sets_etag_header(self):
        response = self.client.get(self.reverse("schedule"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("ETag", response.headers)

    def test_rendered_html_is_valid_html5(self):
        pages = {
            "start.html": self.client.get(
                django_reverse("semester", args=[self.semester])
            ),
            "about.html": self.client.get(django_reverse("about")),
            "schedule.html": self.client.get(self.reverse("schedule")),
            "schedule-advanced.html": self.client.get(
                self.reverse("schedule-advanced")
            ),
            "select_groups.html": self.client.get(self.reverse("change-groups")),
            "error.html": self.client.post(
                self.reverse("change-course"),
                {"submit_add": True, "course_add": "NOT_A_REAL_COURSE"},
            ),
        }

        self.assert_valid_html5(pages)

    def test_schedule_if_none_match_returns_304(self):
        url = self.reverse("schedule")
        first = self.client.get(url)

        second = self.client.get(url, HTTP_IF_NONE_MATCH=first.headers["ETag"])

        self.assertEqual(second.status_code, 304)
        self.assertEqual(second.content, b"")
        self.assertNotIn("Content-Language", second.headers)

    def test_schedule_if_none_match_takes_precedence_over_if_modified_since(self):
        url = self.reverse("schedule")
        first = self.client.get(url)

        response = self.client.get(
            url,
            HTTP_IF_NONE_MATCH='"does-not-match"',
            HTTP_IF_MODIFIED_SINCE=first.headers.get("Last-Modified", ""),
        )

        self.assertEqual(response.status_code, 200)

    def test_change_course(self):
        # FIXME test semester does not exist
        # FIXME test ie handling
        # FIXME test invalid course
        # FIXME test more that 20 warning
        # FIXME test group-help
        # FIXME test error.html

        original_url = self.reverse("schedule-advanced")
        url = self.reverse("change-course")

        post_data = [
            {"submit_add": True, "course_add": "COURSE4"},
            {"submit_name": True, "4-alias": "foo"},
            {
                "submit_name": True,
                "4-alias": "foo bar baz foo bar baz foo bar baz "
                + "foo bar baz foo bar baz foo bar baz",
            },
            {"submit_remove": True, "course_remove": 4},
        ]

        subscriptions = Subscription.objects.filter(student__slug="adamcik")
        subscriptions = subscriptions.order_by("id").values_list()
        subscriptions = list(subscriptions)

        for data in post_data:
            self.client.get(original_url)

            response = self.client.post(url, data)

            self.assertEqual(response.status_code, 302)

            new_subscriptions = list(
                Subscription.objects.filter(student__slug="adamcik")
                .order_by("id")
                .values_list()
            )
            self.assertTrue(new_subscriptions != subscriptions)

            subscriptions = new_subscriptions

    def test_change_course_add_empty_input_redirects_to_schedule_advanced(self):
        response = self.client.post(
            self.reverse("change-course"),
            {"submit_add": True, "course_add": ""},
        )

        self.assertRedirects(response, self.reverse("schedule-advanced"))

    @override_settings(TIMETABLE_ENABLE_IF_MODIFIED_SINCE=True)
    def test_change_course_remove_invalidates_schedule_data_cache(self):
        schedule_url = self.reverse("schedule-advanced")
        change_url = self.reverse("change-course")

        subscriptions = Subscription.objects.filter(
            student__slug="adamcik",
            course__semester__year=2009,
            course__semester__type="spring",
        ).order_by("course__id")

        self.assertGreaterEqual(subscriptions.count(), 2)

        remove_course_id = subscriptions.last().course_id
        remove_course_code = subscriptions.last().course.code

        shared_last_modified = timezone.make_aware(
            datetime.datetime(2009, 1, 1, 12, 0, 0)
        )
        subscriptions.update(last_modified=shared_last_modified)

        cache.clear()

        response = self.client.get(schedule_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, remove_course_code)
        self.assertIn("Last-Modified", response.headers)
        if_modified_since = response.headers["Last-Modified"]

        response = self.client.post(
            change_url,
            {"submit_remove": True, "course_remove": str(remove_course_id)},
        )
        self.assertEqual(response.status_code, 302)

        response = self.client.get(
            schedule_url,
            HTTP_IF_MODIFIED_SINCE=if_modified_since,
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, remove_course_code)

    @override_settings(TIMETABLE_ENABLE_IF_MODIFIED_SINCE=True)
    def test_change_course_in_other_semester_does_not_invalidate_current_schedule(self):
        spring_schedule_url = self.reverse("schedule-advanced")
        fall_change_url = django_reverse(
            "change-course",
            args=[self.next_schedule.semester, self.next_schedule.student.slug],
        )

        response = self.client.get(spring_schedule_url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Last-Modified", response.headers)
        if_modified_since = response.headers["Last-Modified"]

        response = self.client.post(
            fall_change_url,
            {"submit_add": True, "course_add": "COURSE4"},
        )
        self.assertEqual(response.status_code, 302)

        response = self.client.get(
            spring_schedule_url,
            HTTP_IF_MODIFIED_SINCE=if_modified_since,
        )
        self.assertEqual(response.status_code, 304)

    @override_settings(TIMETABLE_ENABLE_IF_MODIFIED_SINCE=True)
    def test_schedule_if_modified_since_returns_304_after_change_course_mutation(self):
        schedule_url = self.reverse("schedule-advanced")
        change_url = self.reverse("change-course")

        response = self.client.get(schedule_url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Last-Modified", response.headers)
        if_modified_since = response.headers["Last-Modified"]

        response = self.client.post(
            change_url,
            {"submit_add": True, "course_add": "COURSE4"},
        )
        self.assertEqual(response.status_code, 302)

        response = self.client.get(
            schedule_url,
            HTTP_IF_MODIFIED_SINCE=if_modified_since,
        )
        self.assertEqual(response.status_code, 200)

    def test_change_course_creates_schedule_row_with_version_bump(self):
        schedule_url = self.reverse("schedule-advanced")
        change_url = self.reverse("change-course")

        Schedule.objects.filter(
            semester__year=2009,
            semester__type="spring",
            student__slug="adamcik",
        ).delete()

        self.client.get(schedule_url)
        response = self.client.post(
            change_url,
            {"submit_add": True, "course_add": "COURSE4"},
        )
        self.assertEqual(response.status_code, 302)

        row = Schedule.objects.get(
            semester__year=2009,
            semester__type="spring",
            student__slug="adamcik",
        )
        self.assertEqual(row.version, 1)

    def test_change_course_increments_schedule_version_on_each_mutation(self):
        schedule_url = self.reverse("schedule-advanced")
        change_url = self.reverse("change-course")

        student = Student.objects.get(slug="adamcik")
        semester = Semester.objects.get(year=2009, type="spring")
        row, _ = Schedule.objects.get_or_create(
            semester_id=semester.id,
            student_id=student.id,
            defaults={"version": 0},
        )
        row.version = 0
        row.save(update_fields=["version"])

        self.client.get(schedule_url)

        response = self.client.post(
            change_url,
            {"submit_add": True, "course_add": "COURSE4"},
        )
        self.assertEqual(response.status_code, 302)

        row.refresh_from_db()
        self.assertEqual(row.version, 1)

        remove_course_id = Subscription.objects.get(
            student__slug="adamcik",
            course__semester__year=2009,
            course__semester__type="spring",
            course__code="COURSE4",
        ).course_id

        response = self.client.post(
            change_url,
            {"submit_remove": True, "course_remove": str(remove_course_id)},
        )
        self.assertEqual(response.status_code, 302)

        row.refresh_from_db()
        self.assertEqual(row.version, 2)

    def test_change_course_updates_schedule_last_modified_on_existing_row(self):
        schedule_url = self.reverse("schedule-advanced")
        change_url = self.reverse("change-course")

        student = Student.objects.get(slug="adamcik")
        semester = Semester.objects.get(year=2009, type="spring")
        row, _ = Schedule.objects.get_or_create(
            semester_id=semester.id,
            student_id=student.id,
            defaults={"version": 0},
        )

        baseline = timezone.make_aware(datetime.datetime(2009, 1, 1, 12, 0, 0))
        Schedule.objects.filter(id=row.id).update(version=0, last_modified=baseline)

        self.client.get(schedule_url)
        response = self.client.post(
            change_url,
            {"submit_add": True, "course_add": "COURSE4"},
        )
        self.assertEqual(response.status_code, 302)

        row.refresh_from_db()
        self.assertEqual(row.version, 1)
        self.assertGreater(row.last_modified, baseline)

    @override_settings(TIMETABLE_ENABLE_IF_MODIFIED_SINCE=True)
    def test_delete_mutation_returns_200_for_old_if_modified_since(self):
        schedule_url = self.reverse("schedule-advanced")
        change_url = self.reverse("change-course")

        response = self.client.get(schedule_url)
        self.assertEqual(response.status_code, 200)
        old_if_modified_since = response.headers["Last-Modified"]

        remove_course_id = (
            Subscription.objects.filter(
                student__slug="adamcik",
                course__semester__year=2009,
                course__semester__type="spring",
            )
            .order_by("course_id")
            .values_list("course_id", flat=True)
            .first()
        )
        self.assertIsNotNone(remove_course_id)

        response = self.client.post(
            change_url,
            {"submit_remove": True, "course_remove": str(remove_course_id)},
        )
        self.assertEqual(response.status_code, 302)

        response = self.client.get(
            schedule_url,
            HTTP_IF_MODIFIED_SINCE=old_if_modified_since,
        )
        self.assertEqual(response.status_code, 200)

    @override_settings(
        TIMETABLE_ENABLE_IF_MODIFIED_SINCE=True,
        TIMETABLE_SNAPSHOT_CACHE_DISK_TTL=7 * 24 * 60 * 60,
    )
    def test_change_course_invalidates_disk_backed_snapshot_metadata(self):
        schedule_url = self.reverse("schedule-advanced")
        change_url = self.reverse("change-course")
        snapshot_key = schedule_snapshot_cache_key(self.semester, self.student.slug)

        response = self.client.get(schedule_url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Last-Modified", response.headers)
        old_if_modified_since = response.headers["Last-Modified"]
        self.assertIsNotNone(caches["disk"].get(snapshot_key))

        caches["default"].clear()

        response = self.client.post(
            change_url,
            {"submit_add": True, "course_add": "COURSE4"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIsNone(caches["disk"].get(snapshot_key))

        response = self.client.get(
            schedule_url,
            HTTP_IF_MODIFIED_SINCE=old_if_modified_since,
        )
        self.assertEqual(response.status_code, 200)

    def test_schedule_with_warm_cache_force_reload_makes_no_queries(self):
        schedule_url = self.reverse("schedule")
        cache.clear()

        response = self.client.get(schedule_url)
        self.assertEqual(response.status_code, 200)

        with self.assertNumQueries(0):
            response = self.client.get(
                schedule_url,
                HTTP_CACHE_CONTROL="no-cache",
            )

        self.assertEqual(response.status_code, 200)

    @override_settings(TIMETABLE_SCHEDULE_CACHE_DURATION=datetime.timedelta(seconds=60))
    def test_schedule_cache_hit_preserves_csp_nonces(self):
        schedule_url = self.reverse("schedule")
        cache.clear()
        caches["disk"].clear()

        first = self.client.get(schedule_url)
        self.assertEqual(first.status_code, 200)
        self.assertIn("miss", first.headers["X-Cache"])

        second = self.client.get(schedule_url)
        self.assertEqual(second.status_code, 200)
        self.assertIn("hit", second.headers["X-Cache"])

        policy = second.headers["Content-Security-Policy"]
        script_match = re.search(r"script-src 'self' 'nonce-([^']+)'", policy)
        style_match = re.search(r"style-src  'self' 'nonce-([^']+)'", policy)

        self.assertIsNotNone(script_match)
        self.assertIsNotNone(style_match)

        content = second.content.decode()
        self.assertIn(f'nonce="{script_match.group(1)}"', content)
        self.assertIn(f'nonce="{style_match.group(1)}"', content)

    def test_schedule_week_with_warm_cache_force_reload_makes_no_queries(self):
        schedule_week_url = self.reverse("schedule-week", 1)
        cache.clear()

        response = self.client.get(schedule_week_url)
        self.assertEqual(response.status_code, 200)

        with self.assertNumQueries(0):
            response = self.client.get(
                schedule_week_url,
                HTTP_CACHE_CONTROL="no-cache",
            )

        self.assertEqual(response.status_code, 200)

    def test_schedule_force_reload_week_after_non_week_warm_makes_no_queries(self):
        schedule_url = self.reverse("schedule")
        schedule_week_url = self.reverse("schedule-week", 1)
        cache.clear()

        response = self.client.get(schedule_url)
        self.assertEqual(response.status_code, 200)

        with self.assertNumQueries(0):
            response = self.client.get(
                schedule_week_url,
                HTTP_CACHE_CONTROL="no-cache",
            )

        self.assertEqual(response.status_code, 200)

    def test_schedule_force_reload_non_week_after_week_warm_makes_no_queries(self):
        schedule_url = self.reverse("schedule")
        schedule_week_url = self.reverse("schedule-week", 1)
        cache.clear()

        response = self.client.get(schedule_week_url)
        self.assertEqual(response.status_code, 200)

        with self.assertNumQueries(0):
            response = self.client.get(
                schedule_url,
                HTTP_CACHE_CONTROL="no-cache",
            )

        self.assertEqual(response.status_code, 200)

    def test_change_course_invalid_course_renders_error(self):
        url = self.reverse("change-course")

        response = self.client.post(
            url,
            {"submit_add": True, "course_add": "NOT_A_REAL_COURSE"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "error.html")

    def test_change_groups(self):
        # FIXME test for courses without groups

        original_url = self.reverse("schedule-advanced")
        url = self.reverse("change-groups")

        post_data = [
            {"1-groups": "1", "2-groups": "", "3-groups": "2"},
            {"1-groups": "", "2-groups": "", "3-groups": ""},
            {"1-groups": ("1", "2"), "2-groups": "", "3-groups": "2"},
        ]

        groups = list(
            Group.objects.filter(subscription__student__slug="adamcik")
            .order_by("id")
            .values_list()
        )

        for data in post_data:
            self.client.get(original_url)

            response = self.client.post(url, MultiValueDict(data))

            self.assertTrue(response["Location"].endswith(original_url))
            self.assertEqual(response.status_code, 302)

            new_groups = list(
                Group.objects.filter(subscription__student__slug="adamcik")
                .order_by("id")
                .values_list()
            )
            self.assertTrue(groups != new_groups)

            groups = new_groups

    def test_change_lectures(self):
        # FIXME test nulling out excludes

        original_url = self.reverse("schedule-advanced")
        url = self.reverse("change-lectures")

        post_data = [
            {"exclude": ("2", "3", "8")},
            {"exclude": ("2")},
            # {}, # FIXME add to test
            {"exclude": ("2", "3", "8", "9", "7", "10", "11", "4", "5", "6")},
            {"exclude": ("2")},
            {"exclude": ("2", "3", "8")},
        ]

        lectures = list(
            Lecture.objects.filter(excluded_from__student__slug="adamcik")
            .order_by("id")
            .values_list()
        )

        for data in post_data:
            self.client.get(original_url)

            response = self.client.post(url, MultiValueDict(data))

            self.assertTrue(response["Location"].endswith(original_url))
            self.assertEqual(response.status_code, 302)

            new_lectures = list(
                Lecture.objects.filter(excluded_from__student__slug="adamcik")
                .order_by("id")
                .values_list()
            )
            self.assertTrue(lectures != new_lectures)

            lectures = new_lectures

    def test_course_query(self):
        url = django_reverse("course-query", args=[self.semester])

        response = self.client.get(url)

        self.assertEqual(b"", response.content)

        response = self.client.get(url, {"q": "COURSE"})
        lines = response.content.split(b"\n")

        self.assertEqual(b"COURSE1|Course 1 full name", lines[0])
        self.assertEqual(b"COURSE2|Course 2 full name", lines[1])
        self.assertEqual(b"COURSE3|Course 3 full name", lines[2])
        self.assertEqual(b"COURSE4|Course 4 full name", lines[3])

        response = self.client.get(url, {"q": "COURSE", "limit": 2})
        lines = [line for line in response.content.split(b"\n") if line]
        self.assertEqual(2, len(lines))

        response = self.client.get(
            url,
            {"q": "COURSE", "limit": 2},
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(2, len(response.json()))
