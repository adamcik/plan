# This file is part of the plan timetable generator, see LICENSE for details.

from __future__ import absolute_import
import os

"""WSGI config for plan project.

This module contains the WSGI application used by Django's development server
and any production WSGI deployments. It should expose a module-level variable
named ``application``. Django's ``runserver`` and ``runfcgi`` commands discover
this application via the ``WSGI_APPLICATION`` setting.
"""

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "plan.settings")

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
