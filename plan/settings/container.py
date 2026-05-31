# This file is part of the plan timetable generator, see LICENSE for details.

import os

import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

from . import env
from plan.settings.base import *  # noqa: F403

SECRET_KEY = env.get("DJANGO_SECRET_KEY", "container-dev-key")
DEBUG = env.get_bool("DJANGO_DEBUG", False)
DEBUG_TOOLBAR_ENABLED = env.get_bool("DJANGO_DEBUG_TOOLBAR", False)
COMPRESS_ENABLED = True
COMPRESS_OFFLINE = True

if DEBUG:
    MIDDLEWARE = (*MIDDLEWARE, "plan.common.middleware.text_debug_middleware")

if DEBUG_TOOLBAR_ENABLED:
    INSTALLED_APPS = (*INSTALLED_APPS, "debug_toolbar")
    MIDDLEWARE = ("debug_toolbar.middleware.DebugToolbarMiddleware", *MIDDLEWARE)
    DEBUG_TOOLBAR_CONFIG = {
        "SHOW_TOOLBAR_CALLBACK": lambda request: True,
    }

if (sentry_dsn := env.get("SENTRY_DSN", None)) is not None:
    sentry_sdk.init(
        dsn=sentry_dsn,
        environment=env.get("SENTRY_ENVIRONMENT", "production"),
        integrations=[
            DjangoIntegration(
                middleware_spans=True,
                cache_spans=True,
            )
        ],
        traces_sample_rate=env.get_float("SENTRY_TRACES_SAMPLE_RATE", 0.001),
    )

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env.get("PGDATABASE", "plan"),
        "USER": env.get("PGUSER", "plan"),
        "PASSWORD": env.get("PGPASSWORD", ""),
        "HOST": env.get("PGHOST", "127.0.0.1"),
        "PORT": env.get("PGPORT", "5432"),
        "CONN_MAX_AGE": env.get_int("PGCONN_MAX_AGE", 0),
    }
}

BASE_DIR = env.get("PLAN_BASE_DIR", "/var/lib/plan")
CACHE_DIR = env.get("PLAN_CACHE_DIR", "/var/cache/plan")

STATIC_ROOT = env.get("PLAN_STATIC_ROOT", os.path.join(BASE_DIR, "static"))
COMPRESS_ROOT = STATIC_ROOT

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": os.path.join(CACHE_DIR, "default"),
        "KEY_PREFIX": "container",
    },
    "ical": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": os.path.join(CACHE_DIR, "ical"),
        "TIMEOUT": timedelta(days=90).total_seconds(),
        "KEY_PREFIX": "container-ical",
        "OPTIONS": {
            "MAX_ENTRIES": 150000,
        },
    },
    "scraper": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": os.path.join(CACHE_DIR, "scraper"),
        "TIMEOUT": timedelta(days=7).total_seconds(),
        "KEY_PREFIX": "container-scraper",
        "OPTIONS": {
            "MAX_ENTRIES": 500000,
        },
    },
}

if (memcached_location := env.get("MEMCACHED_LOCATION", None)) is not None:
    CACHES["default"] = {
        "BACKEND": "django.core.cache.backends.memcached.PyLibMCCache",
        "LOCATION": memcached_location,
        "KEY_PREFIX": env.get("MEMCACHED_KEY_PREFIX", "container"),
    }

ALLOWED_HOSTS = env.get_csv("DJANGO_ALLOWED_HOSTS", ["127.0.0.1", "localhost"])
CSRF_TRUSTED_ORIGINS = env.get_csv("DJANGO_CSRF_TRUSTED_ORIGINS")
USE_X_FORWARDED_HOST = env.get_bool("DJANGO_USE_X_FORWARDED_HOST", True)

if (secure_proxy := env.get("DJANGO_SECURE_PROXY_SSL_HEADER", None)) is not None:
    header, _, value = secure_proxy.partition(",")
    header = header.strip()
    value = value.strip()
    if header and value:
        SECURE_PROXY_SSL_HEADER = (header, value)

EMAIL_SUBJECT_PREFIX = env.get("EMAIL_SUBJECT_PREFIX", "")
TIMETABLE_INSTITUTION = env.get("TIMETABLE_INSTITUTION", TIMETABLE_INSTITUTION)
TIMETABLE_PUBLIC_HOST = env.get("TIMETABLE_PUBLIC_HOST", TIMETABLE_PUBLIC_HOST)
STATIC_URL = env.get("STATIC_URL", STATIC_URL)
COMPRESS_URL = STATIC_URL


LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        }
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": env.get("DJANGO_LOG_LEVEL", "INFO"),
        },
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
        "django.server": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
