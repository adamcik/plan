# This file is part of the plan timetable generator, see LICENSE for details.

import getpass
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
    "scraper": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "KEY_PREFIX": "test-scraper",
    },
}

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("PGDATABASE", "postgres"),
        "USER": os.environ.get("PGUSER", getpass.getuser()),
        "PASSWORD": os.environ.get("PGPASSWORD", ""),
        "HOST": os.environ.get("PGHOST", "127.0.0.1"),
        "PORT": os.environ.get("PGPORT", "5432"),
    }
}

TEST_RUNNER = "plan.testing.runner.PostgresTestRunner"
