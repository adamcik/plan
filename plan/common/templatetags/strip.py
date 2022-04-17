# This file is part of the plan timetable generator, see LICENSE for details.

import re

from django import template
from django.template import defaultfilters

register = template.Library()


@register.filter
@defaultfilters.stringfilter
def striphttp(value):
    return re.sub(r"^https?://(www\.)?", "", value)


@register.tag(name="stripspace")
def do_stripspace(parser, token):
    nodelist = parser.parse(("endstripspace",))
    parser.delete_first_token()
    return StripNode(nodelist)


class StripNode(template.Node):
    regexp = re.compile(r"\s+")

    def __init__(self, nodelist):
        self.nodelist = nodelist

    def render(self, context):
        output = self.nodelist.render(context)
        return re.sub(self.regexp, " ", output).strip()
