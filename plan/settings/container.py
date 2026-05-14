import os

import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

from plan.settings.base import *


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    return int(value)


def _env_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value is None:
        return default
    return float(value)


def _env_csv(name: str, default: list[str] | None = None) -> list[str]:
    value = os.environ.get(name)
    if value is None:
        return list(default or [])
    return [item.strip() for item in value.split(",") if item.strip()]


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "container-dev-key")
DEBUG = _env_bool("DJANGO_DEBUG", False)
DEBUG_TOOLBAR_ENABLED = _env_bool("DJANGO_DEBUG_TOOLBAR", False)
COMPRESS_ENABLED = True

if DEBUG_TOOLBAR_ENABLED:
    INSTALLED_APPS = (*INSTALLED_APPS, "debug_toolbar")
    MIDDLEWARE = ("debug_toolbar.middleware.DebugToolbarMiddleware", *MIDDLEWARE)
    DEBUG_TOOLBAR_CONFIG = {
        "SHOW_TOOLBAR_CALLBACK": lambda request: True,
    }

sentry_dsn = os.environ.get("SENTRY_DSN")
if sentry_dsn:
    sentry_sdk.init(
        dsn=sentry_dsn,
        environment=os.environ.get("SENTRY_ENVIRONMENT", "production"),
        integrations=[
            DjangoIntegration(
                middleware_spans=True,
                cache_spans=True,
            )
        ],
        traces_sample_rate=_env_float("SENTRY_TRACES_SAMPLE_RATE", 0.001),
    )

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("PGDATABASE", "plan"),
        "USER": os.environ.get("PGUSER", "plan"),
        "PASSWORD": os.environ.get("PGPASSWORD", ""),
        "HOST": os.environ.get("PGHOST", "127.0.0.1"),
        "PORT": os.environ.get("PGPORT", "5432"),
        "CONN_MAX_AGE": _env_int("PGCONN_MAX_AGE", 0),
    }
}

BASE_DIR = os.environ.get("PLAN_BASE_DIR", "/var/lib/plan")
CACHE_DIR = os.environ.get("PLAN_CACHE_DIR", "/var/cache/plan")

STATIC_ROOT = os.environ.get("PLAN_STATIC_ROOT", os.path.join(BASE_DIR, "static"))
COMPRESS_ROOT = os.environ.get(
    "PLAN_COMPRESS_ROOT",
    os.path.join(CACHE_DIR, "static"),
)

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

memcached_location = os.environ.get("MEMCACHED_LOCATION")
if memcached_location:
    CACHES["default"] = {
        "BACKEND": "django.core.cache.backends.memcached.PyLibMCCache",
        "LOCATION": memcached_location,
        "KEY_PREFIX": os.environ.get("MEMCACHED_KEY_PREFIX", "container"),
    }

ALLOWED_HOSTS = _env_csv("DJANGO_ALLOWED_HOSTS", ["127.0.0.1", "localhost"])
CSRF_TRUSTED_ORIGINS = _env_csv("DJANGO_CSRF_TRUSTED_ORIGINS")
USE_X_FORWARDED_HOST = _env_bool("DJANGO_USE_X_FORWARDED_HOST", True)

secure_proxy = os.environ.get("DJANGO_SECURE_PROXY_SSL_HEADER")
if secure_proxy:
    header, _, value = secure_proxy.partition(",")
    header = header.strip()
    value = value.strip()
    if header and value:
        SECURE_PROXY_SSL_HEADER = (header, value)

EMAIL_SUBJECT_PREFIX = os.environ.get("EMAIL_SUBJECT_PREFIX", "")
TIMETABLE_INSTITUTION = os.environ.get("TIMETABLE_INSTITUTION", TIMETABLE_INSTITUTION)
STATIC_URL = os.environ.get("STATIC_URL", STATIC_URL)
COMPRESS_URL = os.environ.get("COMPRESS_URL", STATIC_URL)


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
            "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO"),
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
