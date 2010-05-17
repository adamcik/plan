# Copyright 2008, 2009, 2010 Thomas Kongevold Adamcik
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

import logging
import zlib
import base64
from uuid import uuid4

from django.conf import settings
from django.utils.http import int_to_base36
from django.core.cache import cache as django_cache
from django.core.cache.backends.base import  BaseCache

from plan.common.templatetags.slugify import slugify

logger = logging.getLogger('plan.common.cache')

def get_realm(semester, slug=None):
    args = [semester.year, semester.type]
    if slug:
        args.append(slug)

    return ':'.join([slugify(a) for a in args])

def clear_cache(semester, slug):
    django_cache.delete(':'.join([settings.CACHE_PREFIX, get_realm(semester, slug)]))
    django_cache.delete(':'.join([settings.CACHE_PREFIX, get_realm(semester)]))

def compress(value):
    return base64.b64encode(zlib.compress(value))

def decompress(value):
    return zlib.decompress(base64.b64decode(value))

class CacheClass(BaseCache):
    def __init__(self, *args, **kwargs):
        if hasattr(django_cache, 'close'):
            self.close = django_cache.close
        self.language = kwargs.pop('language', None)
        self.realm  = kwargs.pop('realm', None)

    def _get_key(self, key, realm_enabled):
        args = []

        if settings.CACHE_PREFIX:
            args.append(settings.CACHE_PREFIX)

        if realm_enabled and self.realm:
            args.append(self._get_realm_prefix(self.realm))

        args.append(key)

        if self.language:
            args.append(self.language)

        return ':'.join(args)

    def _get_realm_prefix(self, realm):
        logger.debug('Getting realm: %s' % realm)
        realm = ':'.join([settings.CACHE_PREFIX, realm])
        prefix = django_cache.get(realm)

        if prefix:
            return prefix

        prefix = int_to_base36(uuid4().int)
        django_cache.set(realm, prefix, settings.CACHE_TIME_REALM)
        logger.debug('Setting realm: %s' % realm)

        return prefix

    def add(self, key, *args, **kwargs):
        key = self._get_key(key, kwargs.pop('realm', True))
        logger.debug('Adding key: %s' % key)
        return django_cache.add(key, *args, **kwargs)

    def get(self, key, *args, **kwargs):
        key = self._get_key(key, kwargs.pop('realm', True))
        logger.debug('Getting key: %s' % key)
        return django_cache.get(key, *args, **kwargs)

    def set(self, key, *args, **kwargs):
        key = self._get_key(key, kwargs.pop('realm', True))
        logger.debug('Setting key: %s' % key)
        return django_cache.set(key, *args, **kwargs)

    def delete(self, key, *args, **kwargs):
        key = self._get_key(key, kwargs.pop('realm', True))
        logger.debug('Deleting key: %s' % key)
        return django_cache.delete(key, *args, **kwargs)

    def get_many(self, keys, *args, **kwargs):
        realm = kwargs.pop('realm', True)
        for i, key in enumerate(keys):
            keys[i] = self._get_key(key, realm)
        logger.debug('Gettings keys: %s' % keys)
        return django_cache.get_many(keys, *args, **kwargs)

    def has_key(self, key, *args, **kwargs):
        key = self._get_key(key, kwargs.pop('realm', True))
        logger.debug('Checking key: %s' % key)
        return django_cache.has_key(key, *args, **kwargs)
