from django import template
from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape

register = template.Library()

@register.filter
def nbsp(string):
    return mark_safe(conditional_escape(string).replace(' ', '&nbsp;'))
nbsp.is_safe = True
