from django import template
from django.conf import settings

register = template.Library()

@register.inclusion_tag('title.html')
def title(semester, slug, week=None):
    if slug.endswith('s'):
        ending = "'"
    else:
        ending = "'s"

    return {
        'slug': slug,
        'ending': ending,
        'type': semester.get_type_display(),
        'year': semester.year,
        'week': week,
        'no_week': week is None,
    }
