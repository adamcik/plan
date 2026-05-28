# This file is part of the plan timetable generator, see LICENSE for details.

import getpass
import os
from pathlib import Path

from . import env
from plan.settings.base import *

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("PLAN_BASE_DIR", str(BASE_DIR / "data")))


def _load_secret_key() -> str:
    key_path = DATA_DIR / "secret_key"
    if key_path.exists():
        return key_path.read_text().strip()

    raise RuntimeError(
        "Missing Django secret key file at "
        f"{key_path}. "
        'Create it (for example: `python -c "import secrets; print(secrets.token_urlsafe(64))" > data/secret_key`) '
        "or set DJANGO_SECRET_KEY in the environment."
    )


SECRET_KEY = env.get("DJANGO_SECRET_KEY", None) or _load_secret_key()

COMPRESS_ENABLED = False
COMPRESS_OFFLINE = True

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "KEY_PREFIX": "test",
    },
    "ical": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": str(DATA_DIR / "cache" / "ical"),
        "TIMEOUT": timedelta(days=90).total_seconds(),
        "KEY_PREFIX": "test-ical",
        "OPTIONS": {
            "MAX_ENTRIES": 150000,
        },
    },
    "scraper": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": str(DATA_DIR / "cache" / "scraper"),
        "TIMEOUT": timedelta(days=7).total_seconds(),
        "KEY_PREFIX": "test-scraper",
        "OPTIONS": {
            "MAX_ENTRIES": 500000,
        },
    },
}

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env.get("PGDATABASE", "postgres"),
        "USER": env.get("PGUSER", getpass.getuser()),
        "PASSWORD": env.get("PGPASSWORD", ""),
        "HOST": env.get(
            "PGHOST",
            str(DATA_DIR / "pgdata"),
        ),
        "PORT": env.get("PGPORT", ""),
    }
}

TEST_RUNNER = "plan.testing.runner.PostgresTestRunner"

STATIC_ROOT = str(DATA_DIR / "static")
STATIC_URL = "/static/"
COMPRESS_ROOT = STATIC_ROOT
COMPRESS_URL = STATIC_URL
