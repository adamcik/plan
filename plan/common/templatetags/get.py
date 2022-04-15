# This file is part of the plan timetable generator, see LICENSE for details.

from __future__ import absolute_import
from django import template

register = template.Library()


@register.filter
def get(value, key):
    return value.get(key, '')
