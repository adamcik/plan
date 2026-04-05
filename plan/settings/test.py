# This file is part of the plan timetable generator, see LICENSE for details.

import os

from plan.settings.base import *

SECRET_KEY = "test"

COMPRESS_ENABLED = False

# DATABASE_ENGINE = "sqlite3"

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "KEY_PREFIX": "test",
    },
    "ical": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "KEY_PREFIX": "test-ical",
    },
}

if os.environ.get("PLAN_TEST_USE_POSTGRES"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("PGDATABASE", "plan"),
            "USER": os.environ.get("PGUSER", "plan"),
            "PASSWORD": os.environ.get("PGPASSWORD", ""),
            "HOST": os.environ.get("PGHOST", "127.0.0.1"),
            "PORT": os.environ.get("PGPORT", "5432"),
        }
    }
