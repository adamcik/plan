# This file is part of the plan timetable generator, see LICENSE for details.

from datetime import time
from datetime import timedelta

import pkg_resources


def ugettext(s):
    # Dummy translation fuction as we can't import real one
    # http://docs.djangoproject.com/en/1.0/topics/i18n/#id2
    return s


# -- Debug settings:
DEBUG = True

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
DATE_FORMAT = "Y-m-d"

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

LOCALE_PATHS = [pkg_resources.resource_filename("plan", "locales")]

# -- Test:

TEST_RUNNER = "django.test.runner.DiscoverRunner"

# -- App and midleware settings:
MIDDLEWARE = (
    "plan.common.middleware.CspMiddleware",
    "plan.common.middleware.AppendSlashMiddleware",
    "plan.common.middleware.LocaleMiddleware",
    "plan.common.middleware.HtmlMinifyMiddleware",
)

INSTALLED_APPS = (
    "django.contrib.staticfiles",
    "plan.common",
    "plan.scrape",
    "plan.ical",
    "plan.pdf",
    "compressor",
)

# -- Template settings:
# List of callables that know how to import templates from various sources.

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            pkg_resources.resource_filename("plan", "templates"),
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
    "scraper": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": "./cache",
        "TIMEOUT": 60 * 60 * 24 * 7,
        "OPTIONS": {
            "MAX_ENTRIES": 50000,
        },
    },
}

# -- Statifiles settings:
STATIC_ROOT = "./static/"
STATIC_URL = "/static/"

STATICFILES_FINDERS = (
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "compressor.finders.CompressorFinder",
)

STATICFILES_DIRS = [pkg_resources.resource_filename("plan", "static")]

# -- Django compress settings:
if DEBUG:
    COMPRESS_DEBUG_TOGGLE = "no-cache"

COMPRESS_CSS_FILTERS = (
    "compressor.filters.css_default.CssAbsoluteFilter",
    "compressor.filters.datauri.CssDataUriFilter",
    "compressor.filters.cssmin.CSSMinFilter",
)

COMPRESS_DATA_URI_MAX_SIZE = 5 << 10

# -- plan specific settings:

# Name of institution the timetable instalation is for.
TIMETABLE_INSTITUTION = "NTNU"
TIMETABLE_INSTITUTION_SITE = "http://www.ntnu.no/"

TIMETABLE_SHARE_LINKS = (
    (
        "icon-twitter-sign",
        "Twitter",
        "https://twitter.com/share?url=%(url)s&hashtags=timeplan",
    ),
    (
        "icon-facebook-sign",
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

# Hostname to be used in UID of ical events and to identify site, should be a
# constant service-name as UID changes will trigger email notices for new
# events in google calendar etc. Default is to use the HTTP_HOST.
TIMETABLE_HOSTNAME = None

# Where the software can be downloaded.
TIMETABLE_SOURCE_URL = "https://github.com/adamcik/plan/"

# If the syllabus column should be displayed for courses
TIMETABLE_SHOW_SYLLABUS = True

# The CSP report URI to use.
TIMETABLE_REPORT_URI = None

# How long to cache ical feeds for in memory (i.e. not HTTP header caching)
TIMETABLE_ICAL_CACHE_DURATION = timedelta(days=30)
