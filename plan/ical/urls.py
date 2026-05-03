# This file is part of the plan timetable generator, see LICENSE for details.

from django.urls import path

from plan.ical import views

urlpatterns = [
    path("<schedule:schedule>/ical/", views.ical, name="schedule-ical"),
    path(
        "<schedule:schedule>/ical/<ical_type>/", views.ical, name="schedule-ical-type"
    ),
    path(
        "<schedule:schedule>/ical/<ical_type>",
        views.ical,
        name="schedule-ical-type-fallback",
    ),
]
