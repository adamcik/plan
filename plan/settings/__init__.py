from plan.settings.base import *

try:
    from plan.settings.local import *
except ImportError:
    pass
