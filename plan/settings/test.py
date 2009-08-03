from plan.settings.base import *
from plan.settings.local import *

DATABASE_ENGINE = 'sqlite3'

CACHE_BACKEND = 'locmem://'
CACHE_PREFIX = 'test'
