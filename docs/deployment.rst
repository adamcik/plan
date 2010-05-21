Deployment
==========

There are a number of methods for `deploying Django based applications
<http://docs.djangoproject.com/en/1.0/howto/deployment/>`_ Currently the
recommended deployment method is WSGI.

See the :file:`INSTALL` file for a list of package requirements
for Ubuntu/Debian, or use the supplied :file:`requirements.txt`
file to setup the dependencies using `pip <http://pip.openplans.org/>`_.

#. Checkout the code.

   * You might want to place the scripts outside the htaccess folder, e.g. /srv/www/timeplan
   * If scripts are placed outside htdocs, the :file:`timeplan/media` folder
     needs to be symlinked, e.g. :file:`/srv/www/htdocs/timeplan/media` → :file:`/srv/www/timeplan/media`

#. Necessary externals will need to be instaled using pip.
#. Setup apache by following `Configure Apache` and reload apache.
#. Check `<www.yourdomain.com/timeplan/media/css/style.css>`_ to ensure that
   media is setup correctly
#. Setup `local configuration` (:file:`plan/settings/local.py`)
#. Create the database ``./manage.py syncdb``

   * Alternatively use ``./manage.py sqlall auth sites admin sessions
     contenttypes common`` to generate the SQL statements needed to create the
     database manually

#. Create compressed media files ``./manage.py synccompress``

   * This needs to be done whenever the CSS or JS files for the site change
   * Any caches (memcached etc.) will need to be flushed as the cached data
     will point to removed files
   * Memcache flushing: ``echo "flush_all" | nc localhost 11211`` or restart
     memcached.

#. Touch :file:`wsgi/plan.wsgi` to reload the process
#. Check `www.yourdomain.com/timeplan/` and the main page should appear

   * If this doesn't work check the vhost's error-log and/or the apache
     error-log for hints about what is wrong

#. Disable debug mode: open :file:`settings/local.py` and add ``DEBUG = False``

Additional setup
----------------

If using the `Django admin site
<http://docs.djangoproject.com/en/dev/ref/contrib/admin/>`_ , media files
should be available from the directory given in :file:`plan/settings/local.py`
``ADMIN_MEDIA_PREFIX = '/timeplan/media/admin'``.

- From checkout path, create a symlinked folder: ``ln -s
  /usr/share/python-support/python-django/django/contrib/admin/media
  media/admin`` **OR**
- Add an alias to Apache config: ``Alias /timeplan/media/admin/
  /usr/share/python-support/python-django/django/contrib/admin/media``

If necessary, the application can live a hidden life behind a `Behind a reverse proxy`_.

Example Apache config
---------------------

:: 

    RewriteEngine On
    # Add trailing slash
    RewriteRule ^/timeplan$ /timeplan/ [R=permanent,L]

    WSGIScriptAlias /timeplan /path/to/checkout/timeplan/wsgi/plan.wsgi

    Alias /timeplan/media  /path/to/checkout/htdocs/timeplan/media

    <Location /timeplan/media>
        SetHandler None

        # If DEFLATE is all ready turned on globally this is not needed.
        AddOutputFilterByType DEFLATE text/css application/x-javascript
    </Location>

See also `<http://code.google.com/p/modwsgi/wiki/IntegrationWithDjango>`_

.. _proxy:

Behind a reverse proxy
----------------------

To setup the application behind a proxy using mod_proxy, the following
configuration is needed on the frontend server:

::

    <Proxy *> # Enable proxy for vhost
        Order allow,deny
        Allow from all
    </Proxy>

    ProxyRequests Off # Turn of forward proxy

    # Setup reverse-proxy
    ProxyPass /timeplan/ http://backend.server.com/timeplan/
    ProxyPassReverse /timeplan/ http://backend.server.com/timeplan/

If the app is located at the same URL on both frontend and backend everything
should work fine from here on.

If the backend has the app setup at ``/`` and the frontend at ``/timeplan/``
simply add the following :file:`plan/settings/local.py`

::

    FORCE_SCRIPT_NAME = '/timeplan/'
