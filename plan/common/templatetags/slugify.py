#encoding: utf-8

from django.template.defaultfilters import slugify as django_slugify, stringfilter
from django import template

register = template.Library()

@register.filter
@stringfilter
def slugify(text):
    replace_map = (
        (u'Æ', u'Ae'),
        (u'Ø', u'Oe'),
        (u'Å', u'Aa'),
        (u'æ', u'ae'),
        (u'ø', u'oe'),
        (u'å', u'aa'),
    )

    for old, new in replace_map:
        text = text.replace(old, new)

    return django_slugify(text)

slugify.is_safe = True
