import logging
from uuid import uuid4

from django.conf import settings
from django.utils.http import int_to_base36
from django.core.cache import get_cache
from django.core.cache.backends.base import  BaseCache

logger = logging.getLogger()

def get_realm(semester, slug=None):
    args = [semester.year, semester.get_type_display()]
    if slug:
        args.append(slug)

    return ':'.join([str(a) for a in args])

def clear_cache(semester, slug):
    from django.core.cache import cache

    cache.delete(get_realm(semester, slug))
    cache.delete(get_realm(semester))

class CacheClass(BaseCache):
    def __init__(self, *args, **kwargs):
        self.cache = get_cache(settings.CACHE_BACKEND_REAL)

        if hasattr(self.cache, 'close'):
            self.close = self.cache.close

    def _realm(self, key, **kwargs):
        realm = kwargs.pop('realm', None)
        logger.debug('Getting realm: %s' % realm)

        if realm:
            prefix = self.cache.get(realm)

            if not prefix:
                prefix = int_to_base36(uuid4().int)
                self.cache.set(realm, prefix)
                logger.debug('Setting realm: %s' % realm)

            key = ':'.join([prefix, key])

        return (key, kwargs)

    def add(self, key, *args, **kwargs):
        key, kwargs = self._realm(key, **kwargs)
        logger.debug('Adding key: %s' % key)
        return self.cache.add(key, *args, **kwargs)

    def get(self, key, *args, **kwargs):
        key, kwargs = self._realm(key, **kwargs)
        logger.debug('Getting key: %s' % key)
        return self.cache.get(key, *args, **kwargs)

    def set(self, key, *args, **kwargs):
        key, kwargs = self._realm(key, **kwargs)
        logger.debug('Setting key: %s' % key)
        return self.cache.set(key, *args, **kwargs)

    def delete(self, key, *args, **kwargs):
        key, kwargs = self._realm(key, **kwargs)
        logger.debug('Deleting key: %s' % key)
        return self.cache.delete(key, *args, **kwargs)

    def get_many(self, keys, *args, **kwargs):
        key, kwargs = self._realm(key, **kwargs)
        logger.debug('Gettings keys: %s' % keys)
        return self.cache.get_many(keys, *args, **kwargs)

    def has_key(self, key, *args, **kwargs):
        key, kwargs = self._realm(key, **kwargs)
        logger.debug('Checking key: %s' % key)
        return self.cache.has_key(key, *args, **kwargs)
