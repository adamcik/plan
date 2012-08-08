# This file is part of the plan timetable generator, see LICENSE for details.

import dateutil.parser
import decimal
import re
import sys

from django.conf import settings
from django.utils import dates
from django.utils import translation

# Build lookup table with weekdays in all installed languages.
WEEKDAYS = {}
for lang, name in settings.LANGUAGES:
    with translation.override(lang):
        for i in xrange(5):
            day = dates.WEEKDAYS[i].lower()
            assert WEEKDAYS.get(day, i) == i, 'Found conflicting day names.'
            WEEKDAYS[day] = i


def columnify(objects, columns=3):
    objects = map(unicode, objects)
    width = max(map(len, objects))
    border = unicode('+-' + '-+-'.join(['-'*width]*columns) + '-+')
    template = unicode('| ' + ' | '.join(['{:%d}' % width]*columns) + ' |')
    pad_list = lambda i: i + ['']*(columns-len(i))
    lines = []

    while objects:
        lines.append(template.format(*pad_list(objects[:columns])))
        objects = objects[columns:]

    return '\n'.join([border] + lines + [border])


def prompt(message):
    try:
        return raw_input('%s [y/N] ' % message).lower() == 'y'
    except KeyboardInterrupt:
        sys.exit(1)


def compare(old, new):
    old_is_string = isinstance(old, basestring)
    new_is_string = isinstance(new, basestring)

    if (new_is_string and old_is_string and new.strip() == old.strip()):
        return '<whitespace>'
    return '[%s] -> [%s]' % (old, new)


def clean_string(raw_text):
    if raw_text is None:
        return None
    text = raw_text.strip()
    if text[0] in ('"', "'") and text[0] == text[-1]:
        text = text[1:-1].strip()
    return text


def clean_decimal(raw_number):
    if raw_number is None:
        return None
    return decimal.Decimal(raw_number)


def split(value, sep):
    return [i.strip() for i in re.split(sep, value) if i.strip()]


def parse_day_of_week(value):
    """Convert human readable weekday into number.

    Monday=0, ... Saturday and Sunday do not exist.
    """
    return WEEKDAYS.get(value.lower(), None)


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
