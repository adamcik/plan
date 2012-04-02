# This file is part of the plan timetable generator, see LICENSE for details.

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

LOCALE_PATHS = [os.path.join(BASE_PATH, 'locale')]

# -- App and midleware settings:
MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.middleware.locale.LocaleMiddleware',
)

INSTALLED_APPS = (
    'django.contrib.staticfiles',
    'plan.common',
    'plan.scrape',
    'plan.ical',
    'plan.pdf',
    'plan.google',
    'south',
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
    'plan.common.context_processors.source_url',
)

# -- Cache settings:
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'KEY_PREFIX': '',
    },
    'webscraper': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': os.path.join(BASE_PATH, 'cache'),
        'TIMEOUT': 60*60*24,
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
    'compressor.filters.cssmin.CSSMinFilter',
)

# -- South settings:
SKIP_SOUTH_TESTS = True      # Ignore south tests
SOUTH_TESTS_MIGRATE = False  # Don't use south migrations during tests.

# -- plan specific settings:
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

# Maximum number of autocompletere results/
TIMETABLE_AJAX_LIMIT = 100

# How long to remember frontpage cookie.
TIMETABLE_COOKIE_AGE = 60*60*24*7*4

# Max number of courses per timetable.
TIMETABLE_MAX_COURSES = 20

# Assume course codes must end with digits
TIMETABLE_VALID_COURSE_NAMES = r'^[^0-9]+[0-9]+$'

# Hostname to be used in UID of ical events, should be a constant service-name
# as UID changes will trigger email notices for new events in google calendar etc.
TIMETABLE_ICAL_HOSTNAME = socket.getfqdn()

# Where the software can be downloaded.
TIMETABLE_SOURCE_URL = 'http://www.github.com/adamcik/plan/'
