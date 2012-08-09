# This file is part of the plan timetable generator, see LICENSE for details.

from plan.common import tests


class EmptyViewTestCase(tests.BaseTestCase):

    def test_ical(self):
        url = self.url('schedule-ical')
        self.assertEquals(self.client.get(url).status_code, 200)

        for arg in ('exams', 'lectures'):
            url_args = list(self.default_args) + [arg]
            url = self.url('schedule-ical', *url_args)
            self.assertEquals(self.client.get(url).status_code, 200)

        url_args = list(self.default_args) + ['foo']
        url = self.url('schedule-ical', *url_args)
        self.assertEquals(self.client.get(url).status_code, 404)


class ViewTestCase(EmptyViewTestCase):
    fixtures = ['test_data.json', 'test_user.json']
