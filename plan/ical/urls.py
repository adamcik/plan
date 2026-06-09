# This file is part of the plan timetable generator, see LICENSE for details.

from django.urls import path

from plan.ical import views

urlpatterns = [
    path("<semester:semester>/<student:slug>/ical/", views.ical, name="schedule-ical"),
    path(
        "<semester:semester>/<student:slug>/ical/<ical_type>/",
        views.ical,
        name="schedule-ical-type",
    ),
]
