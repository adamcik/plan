# This file is part of the plan timetable generator, see LICENSE for details.

from __future__ import absolute_import
import six.moves.urllib.parse

from django import template

register = template.Library()


@register.filter
def hostname(value):
    result = six.moves.urllib.parse.urlparse(value)
    if not result:
        return None
    elif result.hostname.startswith('www.'):
        return result.hostname[4:]
    else:
        return result.hostname
