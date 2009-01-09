from plan.common.tests import BaseTestCase

class EmptyViewTestCase(BaseTestCase):
    fixtures = ['test_data.json']

    def test_pdf(self):
        args = self.default_args

        pdf_args = [None, 'A4', 'A5', 'A6', 'A7', 'A9']

        for size in pdf_args:
            if size:
                url = self.url('schedule-pdf', *(args + [size]))
            else:
                url = self.url('schedule-pdf', *args)

            response = self.client.get(url)

            if size == 'A9':
                self.assertEquals(response.status_code, 404)
                continue
            else:
                self.assertEquals(response.status_code, 200)

            cached_response = self.get(url)
            self.assertEquals(response.content, cached_response.content)

            self.clear()

            cached_response = self.get(url)
            self.assertEquals(cached_response, None)

class ViewTestCase(EmptyViewTestCase):
    fixtures = ['test_data.json', 'tests_user.json']
