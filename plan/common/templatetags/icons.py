# This file is part of the plan timetable generator, see LICENSE for details.

from django import template
from django.templatetags.static import static
from django.utils.html import format_html

register = template.Library()


@register.simple_tag
def icon(name: str) -> str:
    return format_html(
        '<svg class="icon" aria-hidden="true"><use href="{}#{}"></use></svg>',
        static("icons.svg"),
        name,
    )
