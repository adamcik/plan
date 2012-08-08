# This file is part of the plan timetable generator, see LICENSE for details.

import dateutil.parser
import re
import urllib

from django.conf import settings
from django.utils import dates
from django.utils import translation

# Regexp to use to pull out course code and version.
COURSE_RE = re.compile(r'^([^0-9]+[0-9]+)-(\d+)$')

# Build lookup table with weekdays in all installed languages.
WEEKDAYS = {}
for lang, name in settings.LANGUAGES:
    with translation.override(lang):
        for i in xrange(5):
            day = dates.WEEKDAYS[i].lower()
            assert WEEKDAYS.get(day, i) == i, 'Found conflicting day names.'
            WEEKDAYS[day] = i


def parse_day_of_week(value):
    """Convert human readable weekday into number.

    Monday=0, ... Saturday and Sunday do not exist.
    """
    return WEEKDAYS.get(value.lower(), None)


# TODO(adamcik): since this is ntnu specific this might have to be updated.
def parse_course_code(value):
    """Extract course code and version from NTNU format."""
    if not value or not value.strip():
        return None, None

    match = COURSE_RE.match(value.upper().strip())
    if not match:
        return None, None
    return match.groups()


def parse_time(value):
    """Convert a textual time to a datetime.time instance."""
    if not value or not value.strip():
        return None
    return dateutil.parser.parse(value.strip()).time()


def parse_date(value):
    """Convert a textual date to a datetime.date instance."""
    if not value or not value.strip():
        return None
    return dateutil.parser.parse(value.strip()).date()


def parse_weeks(value):
    """Expand a list of weeks written in shortform."""
    weeks = []
    for v in re.split(r',? ', value):
        if '-' in v:
            start, end = v.split('-')
        else:
            start = end = v
        weeks.extend(range(int(start), int(end)+1))
    return sorted(set(weeks))
