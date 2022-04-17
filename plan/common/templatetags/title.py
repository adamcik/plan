# This file is part of the plan timetable generator, see LICENSE for details.

import re

from django import template
from django.utils import translation

register = template.Library()


@register.inclusion_tag("title.html")
def title(semester, slug, week=None):
    # TODO(adamcik): feels wrong hardcoding this here.
    if translation.get_language() in ["no", "nb", "nn"]:
        ending = norwegian(slug)
    else:
        ending = english(slug)

    return {
        "slug": slug,
        "ending": ending,
        "type": semester.get_type_display(),
        "year": semester.year,
        "week": week,
    }


def render_title(semester, slug, week=None):
    title_template = template.loader.get_template("title.html")
    context = title(semester, slug, week)
    rendered = title_template.render(context)
    rendered = rendered.replace("\n", " ")
    rendered = re.sub(r"\s+", " ", rendered)
    return rendered.strip()


def english(slug):
    if slug.endswith("s"):
        return "'"
    return "'s"


def norwegian(slug):
    if re.search(r"(z|s|x|sch|sh)$", slug):
        return "'"
    return "s"
