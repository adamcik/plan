# This file is part of the plan timetable generator, see LICENSE for details.

import urlparse

from django import template

register = template.Library()


@register.filter
def hostname(value):
    result = urlparse.urlparse(value)
    if not result:
        return None
    elif result.hostname.startswith('www.'):
        return result.hostname[4:]
    else:
        return result.hostname
