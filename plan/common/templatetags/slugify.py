# encoding: utf-8

# This file is part of the plan timetable generator, see LICENSE for details.

from django import template
from django.template import defaultfilters

register = template.Library()

REPLACE_MAP = (
    (u'Æ', u'Ae'),
    (u'Ø', u'O'),
    (u'Å', u'Aa'),
    (u'æ', u'ae'),
    (u'ø', u'o'),
    (u'å', u'aa'),
)


@register.filter
@defaultfilters.stringfilter
def slugify(text):
    for old, new in REPLACE_MAP:
        text = text.replace(old, new)
    return defaultfilters.slugify(text)
slugify.is_safe = True
