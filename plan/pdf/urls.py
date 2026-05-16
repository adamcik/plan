# This file is part of the plan timetable generator, see LICENSE for details.

from django.urls import path

from plan.pdf import views

urlpatterns = [
    path("<semester:semester>/<student:slug>/pdf/", views.pdf, name="schedule-pdf"),
    path(
        "<semester:semester>/<student:slug>/pdf/<week:week>/",
        views.pdf,
        name="schedule-pdf-week",
    ),
    path(
        "<semester:semester>/<student:slug>/pdf/<size>/",
        views.pdf,
        name="schedule-pdf-size",
    ),
    path(
        "<semester:semester>/<student:slug>/pdf/<size>/<week:week>/",
        views.pdf,
        name="schedule-pdf-size-week",
    ),
]
