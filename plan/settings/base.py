# Copyright 2008, 2009, 2010 Thomas Kongevold Adamcik
# 2009 IME Faculty Norwegian University of Science and Technology

# This file is part of Plan.
#
# Plan is free software: you can redistribute it and/or modify
# it under the terms of the Affero GNU General Public License as
# published by the Free Software Foundation, either version 3 of
# the License, or (at your option) any later version.
#
# Plan is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# Affero GNU General Public License for more details.
#
# You should have received a copy of the Affero GNU General Public
# License along with Plan.  If not, see <http://www.gnu.org/licenses/>.

from os.path import realpath, join, dirname
import socket

# Dummy translation fuction as we can't import real one
# http://docs.djangoproject.com/en/1.0/topics/i18n/#id2
ugettext = lambda s: s

# -- Base settings:
BASE_PATH = realpath(join(dirname(__file__), '..', '..'))
SITE_ID = 1

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
        'NAME': join(BASE_PATH, 'plan.sqlite'),
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

LOCALE_PATHS = [join(BASE_PATH, 'locale')]

# -- App and midleware settings:
MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'plan.cache.middleware.CacheMiddleware',
)

INSTALLED_APPS = (
    'django.contrib.staticfiles',
    'plan.common',
    'plan.scrape',
    'plan.ical',
    'plan.pdf',
    'plan.cache',
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
        'LOCATION': join(BASE_PATH, 'cache'),
        'TIMEOUT': 60*60*24,
    },
}

# -- Statifiles settings:
MEDIA_ROOT = join(BASE_PATH, 'media')
STATIC_ROOT = join(BASE_PATH, 'static')
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
TIMETABLE_AJAX_LIMIT = 100
TIMETABLE_COOKIE_AGE = 60*60*24*7*4
TIMETABLE_MAX_COURSES = 20

# Assume course codes must end with digits
TIMETABLE_VALID_COURSE_NAMES = r'^[^0-9]+[0-9]+$'

CACHE_TIME_REALM     = 60*60*24*7*4 #  4w
CACHE_TIME_SCHECULDE = 60*60*24*7   #  1w
CACHE_TIME_SEMESTER  = 10*60        # 10m
CACHE_TIME_HELP      = 2*60         #  2m
CACHE_TIME_AJAX      = 60*60*24*7   #  1w
CACHE_TIME_ABOUT     = 60*60*24*7   #  1w

# Hostname to be used in UID of ical events, should be a constant service-name
# as UID changes will trigger email notices for new events in some cases.
ICAL_HOSTNAME = socket.getfqdn()

# Where the software can be downloaded.
SOURCE_URL = 'http://www.github.com/adamcik/plan/'
