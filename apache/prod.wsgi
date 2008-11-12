import os, sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/..')

if 'DJANGO_SETTINGS_MODULE' not in os.environ:
    os.environ['DJANGO_SETTINGS_MODULE'] = 'plan.settings'

import django.core.handlers.wsgi

application = django.core.handlers.wsgi.WSGIHandler()
