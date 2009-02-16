# pylint: disable-msg=W0614, C0111
# Django settings for plan project.

import os
BASE_PATH = os.path.dirname(os.path.abspath(__file__)) + '/../..'

DEBUG = False
TEMPLATE_DEBUG = DEBUG
LOGGING_OUTPUT_ENABLED = DEBUG
LOGGING_LOG_SQL = DEBUG

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
LANGUAGE_CODE = 'no'

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = False

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
    'plan.common.middleware.CacheMiddleware',
    'plan.common.middleware.UserBasedExceptionMiddleware',
    'plan.common.middleware.TimeViewMiddleware',
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
)

INSTALLED_APPS = (
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.sessions',
    'django.contrib.contenttypes',
    'django.contrib.databrowse',
    'django.contrib.contenttypes',
    'plan.common',
    'plan.scrape',
    'plan.ical',
    'plan.pdf',
)

#TEST_RUNNER = 'plan.common.test_runner.test_runner_with_coverage'

COVERAGE_MODULES = (
    'plan.common.admin',
    'plan.common.cache',
    'plan.common.forms',
    'plan.common.logger',
    'plan.common.managers',
    'plan.common.middleware',
    'plan.common.models',
    'plan.common.timetable',
    'plan.common.urls',
    'plan.common.utils',
    'plan.common.views',
#    'plan.scrape.db',
#    'plan.scrape.studweb',
    'plan.ical.urls',
    'plan.ical.views',
    'plan.pdf.urls',
    'plan.pdf.views',
)

TIMETABLE_MAX_COLORS = 8
TIMETABLE_AJAX_LIMIT = 100
TIMETABLE_COOKIE_AGE = 60*60*24*7*4
TIMETABLE_MAX_COURSES = 20

CACHE_BACKEND = 'locmem://'
CACHE_PREFIX = ''

CACHE_TIME_REALM     = 60*60*24*7*4 #  4w
CACHE_TIME_SCHECULDE = 60*60*24*7   #  1w
CACHE_TIME_FRONTPAGE = 10*60        # 10m
CACHE_TIME_HELP      = 2*60         #  2m
CACHE_TIME_AJAX      = 60*60*24*7   #  1w
