# This file is part of the plan timetable generator, see LICENSE for details.

import copy

from django.conf import settings
from django.test import override_settings


class StrictTemplateVariable:
    def __contains__(self, item):
        return item == "%s"

    def __mod__(self, missing):
        raise RuntimeError(f"Missing template variable or attribute: {missing}")

    def __str__(self):
        raise RuntimeError("Missing template variable or attribute")


def strict_template_variables():
    templates = copy.deepcopy(settings.TEMPLATES)
    for backend in templates:
        if backend.get("BACKEND") != "django.template.backends.django.DjangoTemplates":
            continue
        options = backend.setdefault("OPTIONS", {})
        options["string_if_invalid"] = StrictTemplateVariable()
    return override_settings(TEMPLATES=templates)
