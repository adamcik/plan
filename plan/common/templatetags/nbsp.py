# This file is part of the plan timetable generator, see LICENSE for details.

from __future__ import absolute_import
from django import template
from django.utils import safestring
from django.utils import html

register = template.Library()


@register.filter
def nbsp(string):
    return safestring.mark_safe(
        html.conditional_escape(string).replace(' ', '&nbsp;'))
nbsp.is_safe = True
