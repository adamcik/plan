from django.test import TestCase
from django.conf import settings

from plan.common.cache import cache

class NotUsingDummyCache(TestCase):
    def testNotUsingDummyCache(self):
        self.assertEquals(False, 'dummy' in settings.CACHE_BACKEND)

        self.assertEquals(None, cache.get('test-value'))

        cache.set('test-value', 'foo')

        self.assertEquals('foo', cache.get('test-value'))

        cache.delete('test-value')

        self.assertEquals(None, cache.get('test-value'))
