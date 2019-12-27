# encoding: utf-8
# This file is part of the plan timetable generator, see LICENSE for details.

import datetime
import os.path
import socket

# Dummy translation fuction as we can't import real one
# http://docs.djangoproject.com/en/1.0/topics/i18n/#id2
ugettext = lambda s: s

# -- Base settings:
BASE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))

# -- Debug settings:
DEBUG = True
TEMPLATE_DEBUG = DEBUG

# -- Admin settings:
ADMINS = (
    # ('Your Name', 'your_email@domain.com'),
)

# -- Url settings:
ROOT_URLCONF = 'plan.urls'

# -- Database settings:
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_PATH, 'plan.sqlite'),
    },
}

# -- Time settings:
TIME_ZONE = 'Europe/Oslo'

TIME_FORMAT = "H:i"
DATE_FORMAT = "Y-m-d"

# -- Internationalization settings:
USE_I18N = True

LANGUAGE_CODE = 'en'

LANGUAGES = (
    ('nb', ugettext('Norwegian')),
    ('en', ugettext('English')),
)

# Fallback to given values if users accept the following languages.
LANGUAGE_FALLBACK = {
    'nn': 'nb',  # Nynorsk -> Bokmaal
    'no': 'nb',  # "Norsk" -> Bokmaal
}

LOCALE_PATHS = [os.path.join(BASE_PATH, 'locale')]

# -- Test:

TEST_RUNNER = 'django.test.runner.DiscoverRunner'

# -- App and midleware settings:
MIDDLEWARE_CLASSES = (
    'plan.common.middleware.AppendSlashMiddleware',
    'plan.common.middleware.LocaleMiddleware',
    'plan.common.middleware.HtmlMinifyMiddleware',
)

INSTALLED_APPS = (
    'django.contrib.staticfiles',
    'plan.common',
    'plan.scrape',
    'plan.ical',
    'plan.pdf',
    'compressor',
)

# -- Template settings:
# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    ('django.template.loaders.cached.Loader', (
        'django.template.loaders.filesystem.Loader',
        'django.template.loaders.app_directories.Loader',
    )),
)

TEMPLATE_DIRS = (
    # Put strings here, like "/home/html/django_templates" or
    # "C:/www/django/templates".  Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
    BASE_PATH + '/plan/templates',
)

TEMPLATE_CONTEXT_PROCESSORS = (
    'django.core.context_processors.request',
    'plan.common.context_processors.processor',
)

# -- Cache settings:
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'KEY_PREFIX': '',
    },
    'scraper': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': os.path.join(BASE_PATH, 'cache'),
        'TIMEOUT': 60*60*24*7,
        'OPTIONS': {
            'MAX_ENTRIES': 50000,
        },
    },
}

# -- Statifiles settings:
MEDIA_ROOT = os.path.join(BASE_PATH, 'media')
STATIC_ROOT = os.path.join(BASE_PATH, 'static')
STATIC_URL = '/static/'

STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'compressor.finders.CompressorFinder',
)

STATICFILES_DIRS = (MEDIA_ROOT,)

# -- Django compress settings:
if DEBUG:
    COMPRESS_DEBUG_TOGGLE = 'no-cache'

COMPRESS_CSS_FILTERS = (
    'compressor.filters.css_default.CssAbsoluteFilter',
    'compressor.filters.datauri.CssDataUriFilter',
    'compressor.filters.cssmin.CSSMinFilter',
)

COMPRESS_DATA_URI_MAX_SIZE = 5<<10

# -- plan specific settings:

# Name of institution the timetable instalation is for.
TIMETABLE_INSTITUTION = 'NTNU'
TIMETABLE_INSTITUTION_SITE = 'http://www.ntnu.no/'

TIMETABLE_SHARE_LINKS = (
    ('icon-google-plus-sign', 'Google+', 'https://plus.google.com/share?url=%(url)s'),
    ('icon-twitter-sign', 'Twitter', 'https://twitter.com/share?url=%(url)s&hashtags=timeplan'),
    ('icon-facebook-sign', 'Facebook', 'https://www.facebook.com/sharer/sharer.php?u=%(url)s'),
)

# Colors to use in timetables and throught the site.
TIMETABLE_COLORS = [
    '#B3E2CD',
    '#FDCDAC',
    '#CBD5E8',
    '#F4CAE4',
    '#E6F5C9',
    '#FFF2AE',
    '#F1E2CC',
    '#CCCCCC',
]

# List of tuples containing lecture start and end times to show. All lectures
# will be "pigeonholed" into these slots.
TIMETABLE_SLOTS = [
    (datetime.time( 8,15), datetime.time( 9,0)),
    (datetime.time( 9,15), datetime.time(10,0)),
    (datetime.time(10,15), datetime.time(11,0)),
    (datetime.time(11,15), datetime.time(12,0)),
    (datetime.time(12,15), datetime.time(13,0)),
    (datetime.time(13,15), datetime.time(14,0)),
    (datetime.time(14,15), datetime.time(15,0)),
    (datetime.time(15,15), datetime.time(16,0)),
    (datetime.time(16,15), datetime.time(17,0)),
    (datetime.time(17,15), datetime.time(18,0)),
    (datetime.time(18,15), datetime.time(19,0)),
    (datetime.time(19,15), datetime.time(20,0)),
]

# Available scrapers for loading data into plan. can be run using
# './manage.py scrape <type>' where type is one of the keys bellow.
TIMETABLE_SCRAPERS = {
    'courses': 'plan.scrape.ntnu.web.Courses',
    'courses.tp': 'plan.scrape.ntnu.tp.Courses',
    'exams': 'plan.scrape.ntnu.web.Exams',
    'lectures': 'plan.scrape.ntnu.web.Lectures',
    'lectures.tp': 'plan.scrape.ntnu.tp.Lectures',
    'rooms': 'plan.scrape.ntnu.web.Rooms',
    'rooms.maze': 'plan.scrape.ntnu.maze.Rooms',
    'rooms.web': 'plan.scrape.ntnu.web.Rooms',
}

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
TIMETABLE_SOURCE_URL = 'http://www.github.com/adamcik/plan/'
