#encoding: utf-8

from django.template.defaultfilters import slugify as django_slugify, stringfilter
from django import template

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
@stringfilter
def slugify(text):
    for old, new in REPLACE_MAP:
        text = text.replace(old, new)

    return django_slugify(text)

slugify.is_safe = True
