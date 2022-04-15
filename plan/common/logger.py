# This file is part of the plan timetable generator, see LICENSE for details.

from __future__ import absolute_import
import logging

from django.conf import settings

DATE_TIME_FORMAT = '%Y-%m-%d %H:%M:%S'
CONSOLE_LOG_FORMAT = '[%(asctime)s %(levelname)s] %(message)s'


def init_console(level=None):
    if not level:
        level = getattr(settings, 'LOGLEVEL', logging.INFO)

    logging.basicConfig(
        format=CONSOLE_LOG_FORMAT,
        datefmt=DATE_TIME_FORMAT,
        level=level
    )
