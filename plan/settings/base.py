# Copyright 2008, 2009 Thomas Kongevold Adamcik
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
ugettext = lambda s: s

BASE_PATH = realpath(join(dirname(__file__), '..', '..'))

DEBUG = True
TEMPLATE_DEBUG = DEBUG

LOGGING_OUTPUT_ENABLED = DEBUG
LOGGING_LOG_SQL = DEBUG

DATABASE_ENGINE = 'sqlite3'
DATABASE_NAME = join(BASE_PATH, 'plan.sqlite')

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
  ('no', ugettext('Norwegian')),
  ('en', ugettext('English')),
)

LOCALE_PATHS = [join(BASE_PATH, 'plan', 'locale')]

TIME_FORMAT = "H:i"
DATE_FORMAT = "Y-m-d"

# Absolute path to the directory that holds media.
# Example: "/home/media/media.lawrence.com/"
MEDIA_ROOT = BASE_PATH + '/media'

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash if there is a path component (optional in other cases).
# Examples: "http://media.lawrence.com", "http://example.com/media/"
MEDIA_URL = '/media/'

# URL prefix for admin media -- CSS, JavaScript and images. Make sure to use a
# trailing slash.
# Examples: "http://foo.com/media/", "/media/".
ADMIN_MEDIA_PREFIX = '/media/admin/'

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.load_template_source',
    'django.template.loaders.app_directories.load_template_source',
#     'django.template.loaders.eggs.load_template_source',
)

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
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
    'django.core.context_processors.auth',
    'django.core.context_processors.debug',
    'django.core.context_processors.i18n',
    'django.core.context_processors.media',
    'django.core.context_processors.request',
    'plan.common.context_processors.source_url',
)

INSTALLED_APPS = (
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.contenttypes',
    'django.contrib.contenttypes',
    'compress',
    'plan.common',
    'plan.scrape',
    'plan.ical',
    'plan.pdf',
    'plan.cache',
    'plan.google',
)

COMPRESS = True
COMPRESS_VERSION = True
COMPRESS_AUTO = False
COMPRESS_CSS_FILTERS = None
COMPRESS_JS_FILTERS = None

COMPRESS_CSS = {
    'screen': {
        'source_filenames': ('css/reset-fonts-grids.css',
                             'css/base-min.css',
                             'css/style.css',),
        'output_filename': 'compressed/screen.r?.css',
    },
}
COMPRESS_JS = {
    'all': {
        'source_filenames': ('js/jquery-1.3.1.min.js',
                             'js/jquery.autocomplete.min.js',
                             'js/scripts.js'),
        'output_filename': 'compressed/all.r?.js',
    },
}

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

# Hostname to be used in UID of ical events, should be a constant service-name
# as UID changes will trigger email notices for new events in some cases.
ICAL_HOSTNAME = socket.getfqdn()

# Where the software can be downloaded.
SOURCE_URL = 'https://trac.ime.ntnu.no/timeplan'
