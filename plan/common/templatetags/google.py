from django import template
from django.conf import settings

register = template.Library()

@register.inclusion_tag('googleanalytics.html', takes_context=True)
def googleanalytics(context):
    return {
        'code': getattr(settings, 'GOOGLE_ANALYTICS_CODE', False),
        'secure': 'request' in context and context['request'].is_secure(),
    }
