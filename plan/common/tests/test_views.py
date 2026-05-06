# This file is part of the plan timetable generator, see LICENSE for details.

import datetime

from django.core.cache import cache
from django.urls import reverse
from django.utils.datastructures import MultiValueDict
from django.utils import timezone

from plan.common.models import Group, Lecture, Subscription
from plan.common.tests import BaseTestCase


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
        self.assertTrue(response["Location"].endswith("/static/gfx/icons/calendar.png"))


class ViewTestCase(BaseTestCase):
    fixtures = ["test_data.json", "test_user.json"]

    # FIXME check what happens when we do GET against change functions
    # FIXME test adding course that does not exist for a given semester

    def test_index(self):
        response = self.client.get(reverse("frontpage"))
        url = reverse("semester", args=[self.semester])
        self.assertRedirects(response, url)

    def test_shortcut(self):
        response = self.client.get(self.url("shortcut", "adamcik"))
        url = reverse("schedule-week", args=[self.schedule, 1])
        self.assertRedirects(response, url)

        # TODO: Check with other times.

    def test_redirect_room_missing_returns_404(self):
        response = self.client.get(reverse("redirect_room", args=[999999]))

        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")

    def test_redirect_missing_returns_404_for_all_types(self):
        for name in (
            "redirect_room",
            "redirect_course",
            "redirect_syllabus",
            "redirect_stream",
        ):
            response = self.client.get(reverse(name, args=[999999]))

            self.assertEqual(response.status_code, 404)
            self.assertTemplateUsed(response, "404.html")

    def test_schedule_current(self):
        url = reverse("schedule-current", args=[self.schedule])
        response = self.client.get(url)

        self.assertRedirects(
            response, reverse("schedule-week", args=[self.schedule, 1])
        )

        response = self.client.get(
            reverse("schedule-current", args=[self.next_schedule])
        )
        self.assertRedirects(response, reverse("schedule", args=[self.next_schedule]))

    def test_schedule(self):
        # FIXME add group help testing
        # FIXME courses without lectures
        # FIXME test next semester message
        # FIXME test group-help message

        for url in [
            reverse("schedule", args=[self.schedule]),
            reverse("schedule-advanced", args=[self.schedule]),
            reverse("schedule-week", args=[self.schedule, 1]),
            reverse("schedule-week", args=[self.schedule, 2]),
            reverse("schedule", args=[self.schedule]),
        ]:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertTemplateUsed(response, "schedule.html")

    def test_schedule_sets_robots_header(self):
        response = self.client.get(reverse("schedule", args=[self.schedule]))

        self.assertEqual(
            response.headers["X-Robots-Tag"],
            "noindex, nofollow, noarchive",
        )

    def test_change_course(self):
        # FIXME test semester does not exist
        # FIXME test ie handling
        # FIXME test invalid course
        # FIXME test more that 20 warning
        # FIXME test group-help
        # FIXME test error.html

        original_url = reverse("schedule-advanced", args=[self.schedule])
        url = reverse("change-course", args=[self.schedule])

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

    def test_change_course_remove_invalidates_schedule_data_cache(self):
        schedule_url = reverse("schedule-advanced", args=[self.schedule])
        change_url = reverse("change-course", args=[self.schedule])

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

    def test_change_course_invalid_course_renders_error(self):
        url = reverse("change-course", args=[self.schedule])

        response = self.client.post(
            url,
            {"submit_add": True, "course_add": "NOT_A_REAL_COURSE"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "error.html")

    def test_change_groups(self):
        # FIXME test for courses without groups

        original_url = reverse("schedule-advanced", args=[self.schedule])
        url = reverse("change-groups", args=[self.schedule])

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

        original_url = reverse("schedule-advanced", args=[self.schedule])
        url = reverse("change-lectures", args=[self.schedule])

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
        url = reverse("course-query", args=[self.semester])

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
