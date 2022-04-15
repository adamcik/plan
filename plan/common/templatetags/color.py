# This file is part of the plan timetable generator, see LICENSE for details.

from __future__ import absolute_import
from django import template

register = template.Library()


@register.tag(name='color')
def do_color(parser, token):
    try:
        tag_name, value = token.split_contents()
    except ValueError:
        raise template.TemplateSyntaxError(
            "%r tag requires a single argument" % token.contents.split()[0])

    if value[0] == value[-1] and value[0] in ('"', "'"):
        raise template.TemplateSyntaxError(
            "%r tag's argument should not be in quotes" % tag_name)

    return ColorNode(value)


class ColorNode(template.Node):
    def __init__(self, value):
        self.value = template.Variable(value)
        self.color_map = template.Variable('color_map')

    def render(self, context):
        try:
            return self.color_map.resolve(context)[self.value.resolve(context)]
        except template.VariableDoesNotExist:
            return ''
