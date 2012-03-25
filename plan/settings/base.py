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

BASE_PATH = realpath(join(dirname(__file__), '..', '..'))

DEBUG = True
TEMPLATE_DEBUG = DEBUG

LOGGING_OUTPUT_ENABLED = DEBUG
LOGGING_LOG_SQL = DEBUG

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': join(BASE_PATH, 'plan.sqlite'),
    },
}

USE_ETAGS = True

ADMINS = (
    # ('Your Name', 'your_email@domain.com'),
)

MANAGERS = ADMINS

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be avilable on all operating systems.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'Europe/Oslo'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en'

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

LANGUAGES = (
  ('nb', ugettext('Norwegian')),
  ('en', ugettext('English')),
)

LOCALE_PATHS = [join(BASE_PATH, 'plan', 'locale')]

TIME_FORMAT = "H:i"
DATE_FORMAT = "Y-m-d"

MEDIA_ROOT = join(BASE_PATH, 'media')
STATIC_ROOT = join(BASE_PATH, 'static')
STATIC_URL = '/static/'

ADMIN_MEDIA_PREFIX = STATIC_URL + "admin/"

STATICFILES_FINDERS = (
    'staticfiles.finders.AppDirectoriesFinder',
    'staticfiles.finders.FileSystemFinder',
    'staticfiles.finders.LegacyAppDirectoriesFinder',
    'compressor.finders.CompressorFinder',
)

STATICFILES_DIRS = (MEDIA_ROOT,)

COMPRESS = True

COMPRESS_OFFLINE = True

if DEBUG:
    COMPRESS_DEBUG_TOGGLE = 'no-cache'

COMPRESS_CSS_FILTERS = (
    'compressor.filters.css_default.CssAbsoluteFilter',
    'compressor.filters.cssmin.CSSMinFilter',
)

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
)

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'plan.cache.middleware.CacheMiddleware',
    'plan.common.middleware.UserBasedExceptionMiddleware',
    'plan.common.middleware.PlainContentMiddleware',
)

ROOT_URLCONF = 'plan.urls'

TEMPLATE_DIRS = (
    # Put strings here, like "/home/html/django_templates" or
    # "C:/www/django/templates".  Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
    BASE_PATH + '/plan/templates',
)

TEMPLATE_CONTEXT_PROCESSORS = (
    'django.contrib.auth.context_processors.auth',
    'django.core.context_processors.debug',
    'django.core.context_processors.i18n',
    'django.core.context_processors.media',
    'django.core.context_processors.request',
    'staticfiles.context_processors.static',
    'plan.common.context_processors.source_url',
)

INSTALLED_APPS = (
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.contenttypes',
    'django.contrib.contenttypes',
    'plan.common',
    'plan.scrape',
    'plan.ical',
    'plan.pdf',
    'plan.cache',
    'plan.translation',
    'plan.google',
    'south',
    'compressor',
    'staticfiles',
)

# Don't run any south tests, and don't use south for migration in tests.
SKIP_SOUTH_TESTS = True
SOUTH_TESTS_MIGRATE = False

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

CACHE_BACKEND = 'locmem://'
CACHE_PREFIX = ''

CACHE_TIME_REALM     = 60*60*24*7*4 #  4w
CACHE_TIME_SCHECULDE = 60*60*24*7   #  1w
CACHE_TIME_FRONTPAGE = 10*60        # 10m
CACHE_TIME_HELP      = 2*60         #  2m
CACHE_TIME_AJAX      = 60*60*24*7   #  1w
CACHE_TIME_ABOUT     = 60*60*24*7   #  1w

# Hostname to be used in UID of ical events, should be a constant service-name
# as UID changes will trigger email notices for new events in some cases.
ICAL_HOSTNAME = socket.getfqdn()

# Where the software can be downloaded.
SOURCE_URL = 'http://www.github.com/adamcik/plan/'
