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

import base64
import logging
import time
import zlib

from django.conf import settings
from django.utils import http
from django.utils import translation

from django.core.cache import cache as django_cache
from django.core.cache.backends import base as base_cache

from plan.common.templatetags.slugify import slugify

logger = logging.getLogger('plan.common.cache')

def get_realm(semester, slug=None):
    args = [semester.year, semester.type]
    if slug:
        args.append(slug)

    return ':'.join([slugify(a) for a in args])

def clear_cache(semester, slug):
    logger.debug('Clearing cache for %s %s', semester, slug)
    django_cache.delete(get_realm(semester, slug))
    django_cache.delete(get_realm(semester))

def compress(value):
    return base64.b64encode(zlib.compress(value))

def decompress(value):
    return zlib.decompress(base64.b64decode(value))

class CacheClass(base_cache.BaseCache):
    def __init__(self, *args, **kwargs):
        if hasattr(django_cache, 'close'):
            self.close = django_cache.close
        self.realm  = kwargs.pop('realm', None)
        self.bypass  = kwargs.pop('bypass', False)

    def _get_key(self, key, realm_enabled):
        args = [key, translation.get_language()]

        if realm_enabled and self.realm:
            args.insert(0, self._get_realm_prefix(self.realm))

        return ':'.join(args)

    def _get_realm_prefix(self, realm):
        logger.debug('Getting realm: %s' % realm)
        prefix = django_cache.get(realm)

        if prefix:
            return prefix

        prefix = http.int_to_base36(int(time.time() * 1000))
        django_cache.set(realm, prefix, settings.CACHE_TIME_REALM)
        logger.debug('Setting realm: %s' % realm)

        return prefix

    def get(self, key, *args, **kwargs):
        key = self._get_key(key, kwargs.pop('realm', True))
        if self.bypass:
            logger.debug('Bypassing get for: %s' % key)
            return
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
