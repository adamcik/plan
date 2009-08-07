import logging
from uuid import uuid4

from django.conf import settings
from django.utils.http import int_to_base36
from django.core.cache import cache as django_cache
from django.core.cache.backends.base import  BaseCache

logger = logging.getLogger('plan.common.cache')

def get_realm(semester, slug=None):
    args = [semester.year, semester.type]
    if slug:
        args.append(slug)

    return ':'.join([str(a) for a in args])

def clear_cache(semester, slug):
    from django.core.cache import cache

    cache.delete(':'.join([settings.CACHE_PREFIX, get_realm(semester, slug)]))
    cache.delete(':'.join([settings.CACHE_PREFIX, get_realm(semester)]))

class CacheClass(BaseCache):
    def __init__(self, *args, **kwargs):
        if hasattr(django_cache, 'close'):
            self.close = django_cache.close

    def _realm(self, key, **kwargs):
        realm = kwargs.pop('realm', None)

        logger.debug('Getting realm: %s' % realm)

        if realm:
            realm = ':'.join([settings.CACHE_PREFIX, realm])
            prefix = django_cache.get(realm)

            if not prefix:
                prefix = int_to_base36(uuid4().int)
                django_cache.set(realm, prefix, settings.CACHE_TIME_REALM)
                logger.debug('Setting realm: %s' % realm)

            key = ':'.join([settings.CACHE_PREFIX, prefix, key])

        return (key, kwargs)

    def _prefix(self, key, **kwargs):
        if kwargs.pop('prefix', False):
            key = ':'.join([settings.CACHE_PREFIX, key])

        return (key, kwargs)

    def add(self, key, *args, **kwargs):
        key, kwargs = self._realm(key, **kwargs)
        key, kwargs = self._prefix(key, **kwargs)
        logger.debug('Adding key: %s' % key)
        return django_cache.add(key, *args, **kwargs)

    def get(self, key, *args, **kwargs):
        key, kwargs = self._realm(key, **kwargs)
        key, kwargs = self._prefix(key, **kwargs)
        logger.debug('Getting key: %s' % key)
        return django_cache.get(key, *args, **kwargs)

    def set(self, key, *args, **kwargs):
        key, kwargs = self._realm(key, **kwargs)
        key, kwargs = self._prefix(key, **kwargs)
        logger.debug('Setting key: %s' % key)
        return django_cache.set(key, *args, **kwargs)

    def delete(self, key, *args, **kwargs):
        key, kwargs = self._realm(key, **kwargs)
        key, kwargs = self._prefix(key, **kwargs)
        logger.debug('Deleting key: %s' % key)
        return django_cache.delete(key, *args, **kwargs)

    def get_many(self, keys, *args, **kwargs):
        key, kwargs = self._realm(key, **kwargs)
        key, kwargs = self._prefix(key, **kwargs)
        logger.debug('Gettings keys: %s' % keys)
        return django_cache.get_many(keys, *args, **kwargs)

    def has_key(self, key, *args, **kwargs):
        key, kwargs = self._realm(key, **kwargs)
        key, kwargs = self._prefix(key, **kwargs)
        logger.debug('Checking key: %s' % key)
        return django_cache.has_key(key, *args, **kwargs)

cache = CacheClass()
