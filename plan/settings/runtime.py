# This file is part of the plan timetable generator, see LICENSE for details.

import secrets
from datetime import date, time, timedelta
from importlib.resources import files

import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

from django.utils.safestring import mark_safe

from plan.settings.env import Settings, TelemetryComponent

PLAN_PACKAGE_ROOT = files("plan")


def _sentry_otel_options(components: set[TelemetryComponent]) -> dict[str, str]:
    if TelemetryComponent.TRACING in components:
        return {"instrumenter": "otel"}
    return {}


def ugettext(s):
    # Dummy translation fuction as we can't import real one
    # http://docs.djangoproject.com/en/1.0/topics/i18n/#id2
    return s


SILENCED_SYSTEM_CHECKS = [
    "debug_toolbar.W006",  # Silences the warning about APP_DIRS/app_directories.Loader
]

# -- Debug settings:
DEBUG = False

# -- Admin settings:
ADMINS = (
    # ('Your Name', 'your_email@domain.com'),
)

# -- Url settings:
ROOT_URLCONF = "plan.urls"

# -- Database settings:
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": "./plan.sqlite",
    },
}

# -- Time settings:
TIME_ZONE = "Europe/Oslo"

TIME_FORMAT = "H:i"
SHORT_TIME_FORMAT = "H:i"
DATE_FORMAT = "Y-m-d"
SHORT_DATETIME_FORMAT = "Y-m-d H:i"

# -- Internationalization settings:
USE_I18N = True

LANGUAGE_CODE = "en"

LANGUAGES = (
    ("nb", ugettext("Norwegian")),
    ("en", ugettext("English")),
)

# Fallback to given values if users accept the following languages.
LANGUAGE_FALLBACK = {
    "nn": "nb",  # Nynorsk -> Bokmaal
    "no": "nb",  # "Norsk" -> Bokmaal
}

LOCALE_PATHS = [str(PLAN_PACKAGE_ROOT / "locales")]

# -- Test:

TEST_RUNNER = "django.test.runner.DiscoverRunner"

# -- App and midleware settings:
MIDDLEWARE = (
    "plan.common.middleware.encoding_compatibility_middleware",
    "plan.common.middleware.CspMiddleware",
    "plan.common.middleware.AppendSlashMiddleware",
    "plan.common.middleware.locale_middleware",
    "plan.common.middleware.HtmlMinifyMiddleware",
)

INSTALLED_APPS = (
    "plan.telemetry.apps.TelemetryConfig",
    "django.contrib.staticfiles",
    "plan.common",
    "plan.scrape",
    "plan.ical",
    "plan.pdf",
    "plan.materialized",
    "compressor",
)

# -- Template settings:
# List of callables that know how to import templates from various sources.

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            str(PLAN_PACKAGE_ROOT / "templates"),
        ],
        "OPTIONS": {
            "loaders": (
                (
                    "django.template.loaders.cached.Loader",
                    (
                        "django.template.loaders.filesystem.Loader",
                        "django.template.loaders.app_directories.Loader",
                    ),
                ),
            ),
            "context_processors": (
                "django.template.context_processors.request",
                "plan.common.context_processors.processor",
            ),
        },
    },
]

# -- Cache settings:
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "KEY_PREFIX": "",
    },
    "disk": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": "./cache/disk",
        "TIMEOUT": timedelta(days=7).total_seconds(),
        "KEY_PREFIX": "disk",
        "OPTIONS": {
            "MAX_ENTRIES": 150000,
        },
    },
    "scraper": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": "./cache/scraper",
        "TIMEOUT": timedelta(days=7).total_seconds(),
        "KEY_PREFIX": "scraper",
        "OPTIONS": {
            "MAX_ENTRIES": 500000,
        },
    },
}

# -- Statifiles settings:
STATIC_ROOT = "./static/"
STATIC_URL = "/static/"

STATICFILES_FINDERS = (
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
    "compressor.finders.CompressorFinder",
)

STATICFILES_DIRS = [
    str(PLAN_PACKAGE_ROOT / "static"),
]

# -- Django compress settings:
if DEBUG:
    COMPRESS_DEBUG_TOGGLE = "no-cache"

COMPRESS_STORAGE = "compressor.storage.BrotliCompressorFileStorage"

COMPRESS_FILTERS = {
    "css": (
        "compressor.filters.css_default.CssAbsoluteFilter",
        "compressor.filters.datauri.CssDataUriFilter",
        "compressor.filters.cssmin.CSSMinFilter",
    ),
    "js": ("compressor.filters.jsmin.JSMinFilter",),
}

COMPRESS_DATA_URI_MAX_SIZE = 5 << 10

# -- plan specific settings:

# Name of institution the timetable instalation is for.
TIMETABLE_INSTITUTION = "NTNU"
TIMETABLE_INSTITUTION_SITE = "http://www.ntnu.no/"

TIMETABLE_SHARE_LINKS = (
    (
        "share-twitter",
        "Twitter",
        "https://twitter.com/share?url=%(url)s&hashtags=timeplan",
    ),
    (
        "share-facebook",
        "Facebook",
        "https://www.facebook.com/sharer/sharer.php?u=%(url)s",
    ),
)

# Colors to use in timetables and throught the site.
TIMETABLE_COLORS = [
    "#B3E2CD",
    "#FDCDAC",
    "#CBD5E8",
    "#F4CAE4",
    "#E6F5C9",
    "#FFF2AE",
    "#F1E2CC",
    "#CCCCCC",
]

# List of tuples containing lecture start and end times to show. All lectures
# will be "pigeonholed" into these slots.
TIMETABLE_SLOTS = [
    (time(8, 15), time(9, 0)),
    (time(9, 15), time(10, 0)),
    (time(10, 15), time(11, 0)),
    (time(11, 15), time(12, 0)),
    (time(12, 15), time(13, 0)),
    (time(13, 15), time(14, 0)),
    (time(14, 15), time(15, 0)),
    (time(15, 15), time(16, 0)),
    (time(16, 15), time(17, 0)),
    (time(17, 15), time(18, 0)),
    (time(18, 15), time(19, 0)),
    (time(19, 15), time(20, 0)),
]

# Available scrapers for loading data into plan. can be run using
# './manage.py scrape <type>' where type is one of the keys bellow.
TIMETABLE_SCRAPERS = {
    "courses": "plan.scrape.ntnu.web.Courses",
    "courses.tp": "plan.scrape.ntnu.tp.Courses",
    "exams": "plan.scrape.ntnu.web.Exams",
    "lectures": "plan.scrape.ntnu.web.Lectures",
    "lectures.tp": "plan.scrape.ntnu.tp.Lectures",
    "rooms": "plan.scrape.ntnu.web.Rooms",
    "rooms.maze": "plan.scrape.ntnu.maze.Rooms",
    "rooms.web": "plan.scrape.ntnu.web.Rooms",
    "syllabus": "plan.scrape.ntnu.akademika.Syllabus",
}

TIMETABLE_SCRAPERS_PREFETCH = [
    "plan.scrape.ntnu.web.Courses",
    "plan.scrape.ntnu.web.Lectures",
    "plan.scrape.ntnu.akademika.Syllabus",
]

# Google analytics code to use.
TIMETABLE_ANALYTICS_CODE = None

# Maximum number of autocompletere results/
TIMETABLE_AJAX_LIMIT = 100

# Max number of courses per timetable.
TIMETABLE_MAX_COURSES = 20

# Number of courses to show on frontpage stats.
TIMETABLE_TOP_COURSE_COUNT = 10

# Hostname used for stable identity (notably iCal UID generation). Keep this
# constant; changing it makes calendar clients treat existing events as new.
# Default is to use request host.
TIMETABLE_HOSTNAME = None

# Hostname used for user-facing links in rendered pages (no scheme). Keep this
# separate from TIMETABLE_HOSTNAME so identity host and public host can differ.
# Default is to use request host.
TIMETABLE_PUBLIC_HOST = None

# Where the software can be downloaded.
TIMETABLE_SOURCE_URL = "https://github.com/adamcik/plan/"

# Source to add to external redirects
TIMETABLE_UTM_SOURCE = "timeplan"

# If the syllabus column should be displayed for courses
TIMETABLE_SHOW_SYLLABUS = True

# The optional CSP reporting endpoint.
TIMETABLE_REPORT_URI = None

# How long to cache ical feeds for in caches (i.e. not HTTP header caching)
TIMETABLE_ICAL_CACHE_DURATION = None

# Optional timeout for rendered schedule HTML responses cached in Django's
# default cache. This is separate from HTTP cache headers and separate from the
# schedule snapshot metadata cache below.
TIMETABLE_SCHEDULE_CACHE_DURATION = None

# L1 timeout for cached schedule snapshot metadata (student + semester +
# freshness/version fields) stored in the default cache backend.
TIMETABLE_SNAPSHOT_CACHE_DEFAULT_TTL = None

# Optional L2 timeout for the same schedule snapshot metadata stored in the
# disk cache backend. Set to None to disable the disk fallback layer.
TIMETABLE_SNAPSHOT_CACHE_DISK_TTL = None

# Timeout for semester-wide freshness metadata in the default cache.
TIMETABLE_SEMESTER_FRESHNESS_CACHE_DEFAULT_TTL = None

# Timeouts for other values stored in the default cache backend.
TIMETABLE_LOCATION_CACHE_TTL = None
TIMETABLE_SCHEDULE_DATA_CACHE_TTL = None
TIMETABLE_COURSE_STATS_CACHE_TTL = None

# Freshness updates advance at least one whole second, matching HTTP-date
# precision and keeping If-Modified-Since revalidation safe after mutations.
TIMETABLE_ENABLE_IF_MODIFIED_SINCE = True

TIMETABLE_NOTICE_CUTOFF = date(2025, 8, 24)

TIMETABLE_NOTICE_HTML = mark_safe("""
Vil du drive med IT-systemer på høyt nivå med lav terskel?
<a href="https://itk.samfundet.no/opptak/?utm_source=timeplan">IT-komiteen</a>
<a href="https://www.samfundet.no/verv/1963-it-funksjonaer?utm_source=timeplan">søker</a>
nye medlemmer! Er ikke data noe for deg? Finn andre verv på
<a href="https://samfundet.no/opptak?utm_source=timeplan">samfundet.no</a>
eller <a href="https://apps.uka.no/opptak/?utm_source=timeplan">uka.no</a>.
""")


env = Settings()

TIMETABLE_ICAL_CACHE_DURATION = timedelta(
    seconds=env.timetable_ical_cache_duration_seconds
)

if env.timetable_schedule_cache_duration_seconds is not None:
    TIMETABLE_SCHEDULE_CACHE_DURATION = timedelta(
        seconds=env.timetable_schedule_cache_duration_seconds
    )

TIMETABLE_SNAPSHOT_CACHE_DEFAULT_TTL = env.timetable_snapshot_cache_default_ttl
TIMETABLE_SNAPSHOT_CACHE_DISK_TTL = env.timetable_snapshot_cache_disk_ttl
TIMETABLE_SEMESTER_FRESHNESS_CACHE_DEFAULT_TTL = (
    env.timetable_semester_freshness_cache_default_ttl
)
TIMETABLE_LOCATION_CACHE_TTL = env.timetable_location_cache_ttl
TIMETABLE_SCHEDULE_DATA_CACHE_TTL = env.timetable_schedule_data_cache_ttl
TIMETABLE_COURSE_STATS_CACHE_TTL = env.timetable_course_stats_cache_ttl

DEBUG = env.django_debug
TIMETABLE_REPORT_URI = env.timetable_report_uri

if env.django_secret_key is not None:
    SECRET_KEY = env.django_secret_key.get_secret_value()
elif DEBUG:
    SECRET_KEY = secrets.token_urlsafe(64)
else:
    raise RuntimeError("DJANGO_SECRET_KEY is required when DJANGO_DEBUG is false")

COMPRESS_ENABLED = env.django_compress_enabled
COMPRESS_OFFLINE = env.django_compress_offline

if DEBUG:
    COMPRESS_DEBUG_TOGGLE = "no-cache"
    MIDDLEWARE = (*MIDDLEWARE, "plan.common.middleware.text_debug_middleware")

if env.django_debug_toolbar:
    INSTALLED_APPS = (*INSTALLED_APPS, "debug_toolbar")
    MIDDLEWARE = ("debug_toolbar.middleware.DebugToolbarMiddleware", *MIDDLEWARE)
    DEBUG_TOOLBAR_CONFIG = {
        "SHOW_TOOLBAR_CALLBACK": lambda request: True,
    }

if env.sentry_dsn is not None:
    sentry_sdk.init(
        dsn=env.sentry_dsn.get_secret_value(),
        environment=env.sentry_environment,
        release=env.sentry_release,
        integrations=[
            DjangoIntegration(
                middleware_spans=True,
                cache_spans=True,
            )
        ],
        traces_sample_rate=env.sentry_traces_sample_rate,
        **_sentry_otel_options(env.plan_telemetry_components),
        enable_logs=env.sentry_enable_logs,
    )

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env.pgdatabase,
        "USER": env.pguser,
        "PASSWORD": env.pgpassword.get_secret_value(),
        "HOST": env.pghost,
        "PORT": env.pgport,
        "CONN_MAX_AGE": env.pgconn_max_age,
    }
}

TEST_RUNNER = "plan.testing.runner.PostgresTestRunner"

DATA_DIR = env.plan_base_dir
CACHE_DIR = env.plan_cache_dir

STATIC_ROOT = str(env.plan_static_root or DATA_DIR / "static")
STATIC_URL = env.static_url
COMPRESS_ROOT = STATIC_ROOT
COMPRESS_URL = STATIC_URL

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "KEY_PREFIX": "plan",
    },
    "disk": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": str(CACHE_DIR / "disk"),
        "TIMEOUT": timedelta(days=7).total_seconds(),
        "KEY_PREFIX": "disk",
        "OPTIONS": {
            "MAX_ENTRIES": 150000,
        },
    },
    "scraper": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": str(CACHE_DIR / "scraper"),
        "TIMEOUT": timedelta(days=7).total_seconds(),
        "KEY_PREFIX": env.plan_scraper_cache_key_prefix,
        "OPTIONS": {
            "MAX_ENTRIES": 500000,
        },
    },
}

if env.memcached_location is not None:
    CACHES["default"] = {
        "BACKEND": "django.core.cache.backends.memcached.PyLibMCCache",
        "LOCATION": env.memcached_location,
        "KEY_PREFIX": env.memcached_key_prefix,
    }

ALLOWED_HOSTS = env.django_allowed_hosts
CSRF_TRUSTED_ORIGINS = env.django_csrf_trusted_origins
USE_X_FORWARDED_HOST = env.django_use_x_forwarded_host

if env.django_secure_proxy_ssl_header is not None:
    header, _, value = env.django_secure_proxy_ssl_header.partition(",")
    header = header.strip()
    value = value.strip()
    if header and value:
        SECURE_PROXY_SSL_HEADER = (header, value)

EMAIL_SUBJECT_PREFIX = env.email_subject_prefix

if env.timetable_institution is not None:
    TIMETABLE_INSTITUTION = env.timetable_institution

if env.timetable_public_host is not None:
    TIMETABLE_PUBLIC_HOST = env.timetable_public_host

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
        "structured": {
            "()": "plan.telemetry.logging.StructlogFormatter",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": ("structured" if env.plan_telemetry_components else "simple"),
        }
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": env.django_log_level,
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
