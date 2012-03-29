# This file is part of the plan timetable generator, see LICENSE for details.

from plan.settings.base import *

try:
    from plan.settings.local import *
except ImportError:
    pass
