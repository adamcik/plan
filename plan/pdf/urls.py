# This file is part of the plan timetable generator, see LICENSE for details.

from django.urls import path

from plan.pdf import views

urlpatterns = [
    path("<schedule:schedule>/pdf/", views.pdf, name="schedule-pdf"),
    path("<schedule:schedule>/pdf/<week:week>/", views.pdf, name="schedule-pdf-week"),
    path("<schedule:schedule>/pdf/<size>/", views.pdf, name="schedule-pdf-size"),
    path(
        "<schedule:schedule>/pdf/<size>/<week:week>/",
        views.pdf,
        name="schedule-pdf-size-week",
    ),
]
