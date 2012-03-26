# encoding: utf-8

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
