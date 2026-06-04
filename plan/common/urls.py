# This file is part of the plan timetable generator, see LICENSE for details.

from django.urls import path
from django.views.generic.base import RedirectView
from django.templatetags.static import static

from plan.common import views

urlpatterns = [
    path("", views.frontpage, name="frontpage"),
    path("robots.txt", views.robots_txt, name="robots-txt"),
    path(
        "favicon.ico",
        RedirectView.as_view(url=static("favicon.png"), permanent=True),
        name="favicon",
    ),
    path("<semester:semester>/", views.getting_started, name="semester"),
    path("<semester:semester>/+", views.course_query, name="course-query"),
    path(
        "<semester:semester>/<student:slug>/",
        views.schedule,
        {"all": True},
        name="schedule",
    ),
    path(
        "<semester:semester>/<student:slug>/+",
        views.schedule,
        {"advanced": True},
        name="schedule-advanced",
    ),
    path(
        "<semester:semester>/<student:slug>/current/",
        views.schedule_current,
        name="schedule-current",
    ),
    path(
        "<semester:semester>/<student:slug>/<week:week>/",
        views.schedule,
        name="schedule-week",
    ),
    path(
        "<semester:semester>/<student:slug>/change/",
        views.select_course,
        name="change-course",
    ),
    path(
        "<semester:semester>/<student:slug>/groups/",
        views.select_groups,
        name="change-groups",
    ),
    path(
        "<semester:semester>/<student:slug>/filter/",
        views.select_lectures,
        name="change-lectures",
    ),
    path("c/<base58:id>", views.redirect, {"type": "course"}, name="redirect_course"),
    path(
        "s/<base58:id>", views.redirect, {"type": "syllabus"}, name="redirect_syllabus"
    ),
    path("r/<base58:id>", views.redirect, {"type": "room"}, name="redirect_room"),
    path("u/<base58:id>", views.redirect, {"type": "stream"}, name="redirect_stream"),
    path("+", views.about, name="about"),
    path("<student:slug>", views.shortcut, name="shortcut"),
]
