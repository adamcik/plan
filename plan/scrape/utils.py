# This file is part of the plan timetable generator, see LICENSE for details.

import decimal
import re
import sys

import dateutil.parser
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.utils import dates, translation

# Build lookup table with weekdays in all installed languages.
WEEKDAYS = {}
for lang, name in settings.LANGUAGES:
    with translation.override(lang):
        for i in range(5):
            day = dates.WEEKDAYS[i].lower()
            assert WEEKDAYS.get(day, i) == i, "Found conflicting day names."
            WEEKDAYS[day] = i


def columnify(objects, columns=3):
    objects = list(map(str, objects))
    width = max(list(map(len, objects)))
    border = str("+-" + "-+-".join(["-" * width] * columns) + "-+")
    template = str("| " + " | ".join(["{:%d}" % width] * columns) + " |")
    pad_list = lambda i: i + [""] * (columns - len(i))
    lines = []

    while objects:
        lines.append(template.format(*pad_list(objects[:columns])))
        objects = objects[columns:]

    return "\n".join([border] + lines + [border])


def prompt(message):
    try:
        return input("%s [y/N] " % message).lower() == "y"
    except (KeyboardInterrupt, EOFError):
        sys.exit(1)


def compare(old, new):
    if isinstance(old, str) and isinstance(new, str):
        if new.strip() == old.strip():
            return "<whitespace>"

    if isinstance(old, set) and isinstance(new, set):
        added = set()
        same = set()
        removed = set()

        for i in sorted(old | new, key=lambda v: str(v)):
            if i in old and i in new:
                same.add(" %s" % i)
            elif i in new:
                added.add("+%s" % i)
            else:
                removed.add("-%s" % i)

        return ", ".join(sorted(added) + sorted(removed) + sorted(same))

    if old == "":
        old = "<empty>"
    if new == "":
        new = "<empty>"

    return f"{old} --> {new}"


def clean_string(raw_text):
    if not raw_text:
        return raw_text
    text = raw_text.strip()
    if text and text[0] in ('"', "'") and text[0] == text[-1]:
        text = text[1:-1].strip()
    return text


def clean_decimal(raw_number):
    if raw_number is None:
        return None
    return decimal.Decimal(raw_number)


def clean_list(items, clean):
    return list(filter(bool, list(map(clean, items))))


def valid_url(url):
    try:
        validator = URLValidator(schemes=("http", "https"))
        validator(url)
        return True
    except ValidationError:
        return False


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


def parse_weeks(value, sep=r",? "):
    """Expand a list of weeks written in shortform."""
    weeks = []
    for v in re.split(sep, value):
        if "-" in v:
            start, end = v.split("-")
        else:
            start = end = v
        try:
            weeks.extend(list(range(int(start), int(end) + 1)))
        except ValueError:
            pass
    return sorted(set(weeks))
