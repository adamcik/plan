# This file is part of the plan timetable generator, see LICENSE for details.

from django import template
from django.conf import settings

register = template.Library()


@register.inclusion_tag('google/analytics.html', takes_context=True)
def googleanalytics(context):
    return {
        'code': getattr(settings, 'GOOGLE_ANALYTICS_CODE', False),
        'debug': getattr(settings, 'DEBUG', False),
        'secure': 'request' in context and context['request'].is_secure(),
    }
