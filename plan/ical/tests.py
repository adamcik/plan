# Copyright 2008, 2009 Thomas Kongevold Adamcik
# 2009 IME Faculty Norwegian University of Science and Technology

# This file is part of Plan.
#
# Plan is free software: you can redistribute it and/or modify
# it under the terms of the Affero GNU General Public License as
# published by the Free Software Foundation, either version 3 of
# the License, or (at your option) any later version.
#
# Plan is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# Affero GNU General Public License for more details.
#
# You should have received a copy of the Affero GNU General Public
# License along with Plan.  If not, see <http://www.gnu.org/licenses/>.

from plan.common.tests import BaseTestCase

class EmptyViewTestCase(BaseTestCase):

    def test_ical(self):
        from plan.ical.views import get_resources

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
            cache_url  = self.url('schedule-ical')
            cache_url += '+'.join(get_resources(arg))

            response = self.client.get(url)
            self.assertEquals(response.status_code, 200)

            cached_response = self.get(cache_url)

            self.assertEquals(True, cached_response is not None)
            self.assertEquals(response.content, cached_response.content)

            # Repeat to trim cache code
            response = self.client.get(url)
            self.assertEquals(response.status_code, 200)

            self.clear()
            cached_response = self.get(cache_url)
            self.assertEquals(cached_response, None)

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
        response = self.client.get(url, {'plain': True})
        self.assertEquals(response.status_code, 200)

class ViewTestCase(EmptyViewTestCase):
    fixtures = ['test_data.json', 'test_user.json']
