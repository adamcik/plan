# This file is part of the plan timetable generator, see LICENSE for details.

from plan.common import tests
from plan.ical.views import get_resources


class EmptyViewTestCase(tests.BaseTestCase):

    def test_ical(self):

        args = [
            '',
            'exams',
            'deadlines',
            'lectures',

            'lectures+exams',
            'exams+lectures',

            'exams+deadlines',
            'deadlines+exams',

            'lectures+deadlines',
            'deadlines+lectures',

            'lectures+deadlines+exams',
            'deadlines+exams+lectures',
            'exams+lectures+deadlines',

            'lectures+exams+deadlines',
            'exams+deadlines+lectures',
            'deadlines+lectures+exams',

            'deadlines+lectures+exams',
            'lectures+exams+deadlines',
            'exams+deadlines+lectures',
        ]

        for arg in args:
            if arg:
                url_args = list(self.default_args) + [arg]
            else:
                url_args = list(self.default_args)

            url = self.url('schedule-ical', *url_args)

            response = self.client.get(url)
            self.assertEquals(response.status_code, 200)

        args = [
            'exams+exams',
            'deadlines+deadlines',
            'lectures+lectures',

            'lectures+deadlines+exams+lectures',
            'deadlines+exams+lectures+lectures',
            'exams+lectures+deadlines+lectures',
        ]

        for arg in args:
            url_args = list(self.default_args) + [arg]
            url = self.url('schedule-ical', *url_args)

            response = self.client.get(url)
            self.assertEquals(response.status_code, 404)

        url = self.url('schedule-ical')
        response = self.client.get(url)
        self.assertEquals(response.status_code, 200)


class ViewTestCase(EmptyViewTestCase):
    fixtures = ['test_data.json', 'test_user.json']
