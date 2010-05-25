Deployment
==========

There are a number of methods for deploying Django based applications Currently
the recommended deployment method is WSGI.

.. seealso::
 `<http://docs.djangoproject.com/en/dev/howto/deployment/>`_

Getting started
---------------

See the :file:`INSTALL` file for a list of package requirements
for Ubuntu/Debian, or use the supplied :file:`requirements.txt`
file to setup the dependencies using `pip <http://pip.openplans.org/>`_.

#. Checkout the code.

   * You might want to place the scripts outside the htdocs folder, e.g. /srv/www/timeplan
   * If scripts are placed outside htdocs, the :file:`timeplan/media` folder
     needs to be symlinked, e.g. :file:`/srv/www/htdocs/timeplan/media` → 
     :file:`/srv/www/timeplan/media` or made available using the alias
     directive in Apache.

#. Necessary externals will need to be instaled using :command:`pip`.
#. Setup apache by following `Example Apache config`_ and reload apache.
#. Check `<www.example.com/timeplan/media/css/style.css>`_ to ensure that
   media is setup correctly
#. Setup `local configuration` (:file:`plan/settings/local.py`)
#. Create the database ``./manage.py syncdb``

   * Alternatively use ``./manage.py sqlall auth sites admin sessions
     contenttypes common`` to generate the SQL statements needed to create the
     database manually

#. Perform the required database migrations ``./manage.py migrate``
#. Create compressed media files ``./manage.py synccompress``

   * This needs to be done whenever the CSS or JS files for the site change
   * Any caches (memcached etc.) will need to be flushed as the cached data
     will point to removed files
   * Memcache flushing: ``echo "flush_all" | nc localhost 11211`` or restart
     memcached.

#. Touch :file:`wsgi/plan.wsgi` to reload the process
#. Check `www.example.com/timeplan/` and the main page should appear

   * If this doesn't work check the vhost's error-log and/or the apache
     error-log for hints about what is wrong

#. Disable debug mode: open :file:`settings/local.py` and add ``DEBUG = False``

Upgrading
---------

For a regular install that is all ready using :command:`south` the following should
suffice for upgrading to a newer version:

#. Backup your database (and optionally your install).
#. Retrieve the new version from VCS or tar-ball.
#. Check that :file:`requirements.txt` dependencies are met, if you are using
   :command:`virtualenv` and :command:`pip` simply running
   ``pip install -E path/to/virtualenv/dir -r requirements.txt`` should
   suffice.
#. Run ``./manage.py migrate`` to perform any database migrations.
#. Run ``./manage.py synccompress`` to compress any new JS and/or CSS.
#. Run ``touch ../wsgi/plan.wsgi`` to reload the application or restart Apache.
#. Run ``./manage.py flushreakns`` to flush the cache or whatever is appropriate
   for the cache backend you have setup.

.. important::
  If the install hasn't been using :command:`south` the following needs to run to get
  the system in the correct state. As of version ``1.3`` all plan installs are
  expected to use south for migrations.

  * ``1.0`` users need to run ``./manage.py migrate common 0001 --skip`` first
  * ``1.1`` users need to run ``./manage.py migrate common 0035 --skip`` first
  * ``1.2`` users need to run ``./manage.py migrate common 0038 --skip`` first

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

.. seealso::
   `<http://code.google.com/p/modwsgi/wiki/IntegrationWithDjango>`_

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
