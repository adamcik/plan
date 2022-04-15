# This file is part of the plan timetable generator, see LICENSE for details.

from django import template
from django.template import defaultfilters

register = template.Library()

REPLACE_MAP = (
    ('Æ', 'Ae'),
    ('Ø', 'O'),
    ('Å', 'Aa'),
    ('æ', 'ae'),
    ('ø', 'o'),
    ('å', 'aa'),
)


@register.filter
@defaultfilters.stringfilter
def slugify(text):
    for old, new in REPLACE_MAP:
        text = text.replace(old, new)
    return defaultfilters.slugify(text)
slugify.is_safe = True
