# This file is part of the plan timetable generator, see LICENSE for details.

import datetime
from http import HTTPStatus

from django.urls import reverse as django_reverse

from plan.common.models import Course, Group, Lecture
from plan.common.tests import BaseTestCase


class EmptyViewTestCase(BaseTestCase):
    def reverse(self, view, *extra_args):
        return django_reverse(
            view, args=[self.semester, self.student.slug, *extra_args]
        )

    def test_pdf(self):
        pdf_args = [None, "A4", "A5", "A6", "A9", "A7"]

        for size in pdf_args:
            if size:
                url = self.reverse("schedule-pdf-size", size)
            else:
                url = self.reverse("schedule-pdf")

            response = self.client.get(url)
            if size == "A9":
                self.assertEqual(response.status_code, 404)
                continue
            else:
                self.assertEqual(response.status_code, 200)

            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)


class ViewTestCase(EmptyViewTestCase):
    fixtures = ["test_data.json", "test_user.json"]

    def test_pdf_response_is_pdf_document(self):
        response = self.client.get(self.reverse("schedule-pdf"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF-"))

    def test_pdf_rejects_timetable_too_dense_to_render(self):
        course = Course.objects.get(pk=1)
        group = Group.objects.get(pk=1)
        lectures = Lecture.objects.bulk_create(
            [
                Lecture(
                    course=course,
                    day=0,
                    start=datetime.time(8, 15),
                    end=datetime.time(9),
                )
                for _ in range(40)
            ]
        )
        Lecture.groups.through.objects.bulk_create(
            [
                Lecture.groups.through(lecture_id=lecture.id, group_id=group.id)
                for lecture in lectures
            ]
        )

        response = self.client.get(self.reverse("schedule-pdf"))

        self.assertEqual(response.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)
        self.assertEqual(response.headers["Content-Type"], "text/html; charset=utf-8")
        self.assertTemplateUsed(response, "error.html")
        self.assertContains(
            response,
            "This timetable has too many simultaneous activities to export as PDF.",
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        )

    def test_pdf_sets_etag_header(self):
        url = self.reverse("schedule-pdf")

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertIn("ETag", response.headers)

    def test_pdf_if_none_match_returns_304(self):
        url = self.reverse("schedule-pdf")
        first = self.client.get(url)

        second = self.client.get(url, HTTP_IF_NONE_MATCH=first.headers["ETag"])

        self.assertEqual(second.status_code, 304)
        self.assertEqual(second.content, b"")

    def test_pdf_if_none_match_takes_precedence_over_if_modified_since(self):
        url = self.reverse("schedule-pdf")
        first = self.client.get(url)

        response = self.client.get(
            url,
            HTTP_IF_NONE_MATCH='"does-not-match"',
            HTTP_IF_MODIFIED_SINCE=first.headers.get("Last-Modified", ""),
        )

        self.assertEqual(response.status_code, 200)
