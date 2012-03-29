# This file is part of the plan timetable generator, see LICENSE for details.

from django import template
from django.utils import simplejson as json

register = template.Library()


@register.filter(name='json')
def dump_json(value):
    return json.dumps(value)
json.is_safe = True
