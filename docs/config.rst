Setting up a proper environment
===============================

Using the default settings file gives you reasonable sensible settings for
development which rely on a local SQLite database for storage. To allow for
local configuration of the site add a file :file:`plan/settings/local.py`.
This is the file where the settings specific to your site should be kept, this
file should not be checked in to any VCS and is where the software will end up
getting the database credentials.

Example local.py
----------------

::

    DEBUG = True
    TEMPLATE_DEBUG = DEBUG

    ADMINS = (
        ('<Your name here>', '<your email here>'),
    )
    MANAGERS = ADMINS

    # Make this unique, and don't share it with anybody.
    SECRET_KEY = '<Your nice long secret key here>'

    DATABASE_ENGINE = 'mysql' # See Django docs...
    DATABASE_NAME = '<Your db name here>'
    DATABASE_USER = '<Your db user here>'
    DATABASE_HOST = '<Your db host here>'
    DATABASE_PASSWORD = '<Your db password here>'
    DATABASE_OPTIONS = { # Only needed for mySQL
       "init_command": "SET storage_engine=INNODB",
    }

    # This extra set of settings is to connect to
    # the NTNU lecture database.
    MYSQL_NAME = ''
    MYSQL_USER = ''
    MYSQL_PASSWORD = ''
    MYSQL_HOST = ''

    CACHE_BACKEND = 'locmen://' # See Django docs...
    CACHE_PREFIX = '<Your prefix here>' # Should be unique per site

    # Web URL where Django should expect to find media files
    MEDIA_URL = '/timeplan/media/'
    ADMIN_MEDIA_PREFIX = '/timeplan/media/admin/'

    # Hostname to be used in UID of ical events, should be a constant service-name
    # as UID changes will trigger email notices for new events in some cases.
    ICAL_HOSTNAME = '<Your service DNS name here>'

    # Where the software can be downloaded as required by the AGPL
    SOURCE_URL = 'https://github.com/adamcik/plan'

Remember to set ``DEBUG = False`` on all production setups.
