# This file is part of the plan timetable generator, see LICENSE for details.

import os

"""WSGI config for plan project.

This module contains the WSGI application used by Django's development server
and any production WSGI deployments. It should expose a module-level variable
named ``application``. Django's ``runserver`` and ``runfcgi`` commands discover
this application via the ``WSGI_APPLICATION`` setting.
"""

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "plan.settings")

from django.core.wsgi import get_wsgi_application


_django_application = get_wsgi_application()


def application(environ, start_response):
    """Reject paths that violate WSGI's ISO-8859-1 encoding requirement."""
    try:
        for key in ("PATH_INFO", "SCRIPT_NAME"):
            environ.get(key, "").encode("iso-8859-1")
    except UnicodeEncodeError:
        start_response("400 Bad Request", [("Content-Length", "0")])
        return []

    return _django_application(environ, start_response)
