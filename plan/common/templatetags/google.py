# encoding: utf-8

# Copyright 2008, 2009 Thomas Kongevold Adamcik

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
from django.conf import settings

register = template.Library()

@register.inclusion_tag('googleanalytics.html', takes_context=True)
def googleanalytics(context):
    return {
        'code': getattr(settings, 'GOOGLE_ANALYTICS_CODE', False),
        'secure': 'request' in context and context['request'].is_secure(),
    }
