# This file is part of the plan timetable generator, see LICENSE for details.

from django import template
from django.utils import dates

register = template.Library()


@register.filter
def weekday(value):
    try:
        return dates.WEEKDAYS[int(value)]
    except (TypeError, ValueError, KeyError):
        return ""
