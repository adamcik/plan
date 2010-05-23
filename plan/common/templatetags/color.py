# Copyright 2008, 2009 Thomas Kongevold Adamcik
# 2009 IME Faculty Norwegian University of Science and Technology

# This file is part of Plan.
#
# Plan is free software: you can redistribute it and/or modify
# it under the terms of the Affero GNU General Public License as
# published by the Free Software Foundation, either version 3 of
# the License, or (at your option) any later version.
#
# Plan is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# Affero GNU General Public License for more details.
#
# You should have received a copy of the Affero GNU General Public
# License along with Plan.  If not, see <http://www.gnu.org/licenses/>.

from django import template

register = template.Library()

@register.tag(name='color')
def do_color(parser, token):
    try:
        tag_name, value = token.split_contents()
    except ValueError:
        raise template.TemplateSyntaxError, "%r tag requires a single argument" % token.contents.split()[0]
    if value[0] == value[-1] and value[0] in ('"', "'"):
        raise template.TemplateSyntaxError, "%r tag's argument should not be in quotes" % tag_name
    return ColorNode(value)

class ColorNode(template.Node):
    def __init__(self, value):
        self.value = value
    def render(self, context):
        try:
            value = template.Variable(self.value).resolve(context)
            return template.Variable('color_map').resolve(context)[value]
        except template.VariableDoesNotExist:
            return ''
