# This file is part of the plan timetable generator, see LICENSE for details.

from django.urls import reverse as django_reverse

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
