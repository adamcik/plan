# This file is part of the plan timetable generator, see LICENSE for details.

from __future__ import absolute_import
from plan.settings.base import *

SECRET_KEY = 'test'

COMPRESS_ENABLED = False

DATABASE_ENGINE = 'sqlite3'

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'KEY_PREFIX': 'test',
    }
}
