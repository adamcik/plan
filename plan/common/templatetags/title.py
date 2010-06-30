# Copyright 2009, 2010 Thomas Kongevold Adamcik
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

import re

from django import template
from django.utils.translation import get_language

register = template.Library()

@register.inclusion_tag('title.html')
def title(semester, slug, week=None):
    if get_language() in ['no', 'nb', 'nn']:
        ending = norwegian(slug)
    else:
        ending = english(slug)

    return {
        'slug': slug,
        'ending': ending,
        'type': semester.get_type_display(),
        'year': semester.year,
        'week': week,
    }

def render_title(semester, slug, week=None):
    title_template = template.loader.get_template('title.html')
    context = template.Context(title(semester, slug, week))
    rendered = title_template.render(context)
    rendered = rendered.replace('\n', ' ')
    rendered = re.sub('\s+', ' ', rendered)
    return rendered.strip()

def english(slug):
    if slug.endswith('s'):
        return "'"
    return "'s"

def norwegian(slug):
    if re.search(r'(z|s|x|sch|sh)$', slug):
        return "'"
    return "s"
