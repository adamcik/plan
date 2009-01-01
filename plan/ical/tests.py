from plan.common.test import BaseTestCase

class EmptyViewTestCase(BaseTestCase):
    pass

class ViewTestCase(BaseTestCase):
    fixtures = ['test_data.json']
