# This file is part of the plan timetable generator, see LICENSE for details.

import os
import sys

"""WSGI config for plan project.

This module contains the WSGI application used by Django's development server
and any production WSGI deployments. It should expose a module-level variable
named ``application``. Django's ``runserver`` and ``runfcgi`` commands discover
this application via the ``WSGI_APPLICATION`` setting.
"""

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "plan.settings")

project_dir = os.path.dirname(os.path.abspath(__file__)) + '/..'
if project_dir not in sys.path:
    sys.path.append(project_dir)

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
