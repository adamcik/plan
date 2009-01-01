import datetime

from django.test import TestCase

class MockDatetime(datetime.datetime):
    @classmethod
    def now(cls):
        return datetime.datetime(2009, 1, 1)

class BaseTestCase(TestCase):
    def setUp(self):
        self.datetime = datetime.datetime
        datetime.datetime = MockDatetime

    def tearDown(self):
        datetime.datetime = self.datetime

class EmptyViewTestCase(BaseTestCase):
    def test_index(self):
        response = self.client.get('/')

        self.failUnlessEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'start.html')

    def test_shortcut(self):
        response = self.client.get('/adamcik/')

        self.failUnlessEqual(response.status_code, 404)
        self.assertTemplateUsed(response, '404.html')

class ViewTestCase(BaseTestCase):
    fixtures = ['test_data.json']

    def test_index(self):
        pass

    def test_shortcut(self):
        pass

    def test_schedule(self):
        pass

    def test_advanced_schedule(self):
        pass

class TimetableTestCase(BaseTestCase):
    fixtures = ['test_data.json']

    def test_place(self):
        pass

class MangerTestCase(BaseTestCase):
    fixtures = ['test_data.json']

    # FIXME test all custom manager methods

class UtilTestCase(BaseTestCase):
    fixtures = ['test_data.json']

    def test_colormap(self):
        pass

    def test_compact_sequence(self):
        pass

class FormTestCase(BaseTestCase):
    pass
