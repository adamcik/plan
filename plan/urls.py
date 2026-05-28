# This file is part of the plan timetable generator, see LICENSE for details.

from django.conf import settings
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include, path, re_path, register_converter

from plan.common import converters

handler500 = "plan.common.utils.server_error"

register_converter(converters.SemesterConverter, "semester")
register_converter(converters.StudentConverter, "student")
register_converter(converters.WeekNumberConverter, "week")
register_converter(converters.Base58Converter, "base58")

if settings.DEBUG:
    from django.views.generic.base import TemplateView

    urlpatterns = [
        re_path(r"^500/$", TemplateView.as_view(template_name="500.html")),
        re_path(r"^404/$", TemplateView.as_view(template_name="404.html")),
    ]
else:
    urlpatterns = []

urlpatterns += [
    re_path(r"^", include("plan.common.urls")),
    re_path(r"^", include("plan.ical.urls")),
    re_path(r"^", include("plan.pdf.urls")),
]

if "debug_toolbar" in settings.INSTALLED_APPS:
    import debug_toolbar

    urlpatterns += [
        path("__debug__/", include(debug_toolbar.urls)),
    ]

# This will only be active when DEBUG=False or --insecure is set
urlpatterns += staticfiles_urlpatterns()
