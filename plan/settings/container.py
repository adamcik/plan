import os

from plan.settings.base import *


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "container-dev-key")
DEBUG = _env_bool("DJANGO_DEBUG", False)
COMPRESS_ENABLED = True

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

BASE_DIR = os.environ.get("PLAN_BASE_DIR", "/var/lib/plan")

STATIC_ROOT = os.path.join(BASE_DIR, "static")

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": os.path.join(BASE_DIR, "cache", "default"),
        "KEY_PREFIX": "container",
    },
    "ical": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": os.path.join(BASE_DIR, "cache", "ical"),
        "TIMEOUT": timedelta(days=90).total_seconds(),
        "KEY_PREFIX": "container-ical",
        "OPTIONS": {
            "MAX_ENTRIES": 1000000,
        },
    },
    "scraper": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": os.path.join(BASE_DIR, "cache", "scraper"),
        "TIMEOUT": timedelta(days=7).total_seconds(),
        "KEY_PREFIX": "container-scraper",
        "OPTIONS": {
            "MAX_ENTRIES": 500000,
        },
    },
}
