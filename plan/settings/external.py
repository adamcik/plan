# This file is part of the plan timetable generator, see LICENSE for details.

import os

from plan.settings.base import *

# Use this settings module when you want to keep your settings in a central
# place like /etc and run your code from a virtualenv etc.
#
# DJANGO_SETTINGS_MODULE=plan.settings.external EXTERNAL_SETTINGS_FILE=/path/to/settings.py ...

if 'EXTERNAL_SETTINGS_FILE' in os.environ:
    execfile(os.environ['EXTERNAL_SETTINGS_FILE'])
