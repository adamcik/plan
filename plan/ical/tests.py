# This file is part of the plan timetable generator, see LICENSE for details.

from plan.common import tests


class EmptyViewTestCase(tests.BaseTestCase):
    def test_ical(self):
        """This covers the semester not existing."""

        url = self.url("schedule-ical")
        self.assertEqual(self.client.get(url).status_code, 404)

        for arg in ("exams", "lectures"):
            url_args = list(self.default_args) + [arg]
            url = self.url("schedule-ical", *url_args)
            self.assertEqual(self.client.get(url).status_code, 404)

        url_args = list(self.default_args) + ["foo"]
        url = self.url("schedule-ical", *url_args)
        self.assertEqual(self.client.get(url).status_code, 400)


class ViewTestCase(tests.BaseTestCase):
    fixtures = ["test_data.json", "test_user.json"]

    def test_ical(self):
        url = self.url("schedule-ical")
        self.assertEqual(self.client.get(url).status_code, 200)

        for arg in ("exams", "lectures"):
            url_args = list(self.default_args) + [arg]
            url = self.url("schedule-ical", *url_args)
            self.assertEqual(self.client.get(url).status_code, 200)

        url_args = list(self.default_args) + ["foo"]
        url = self.url("schedule-ical", *url_args)
        self.assertEqual(self.client.get(url).status_code, 400)

        # TODO: Test with slug that does not exist?
