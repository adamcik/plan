from django.test import TestCase

class EmptyViewTestCase(TestCase):
    pass

class ViewTestCase(TestCase):
    fixtures = ['test_data.json']
