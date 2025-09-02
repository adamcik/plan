# This file is part of the plan timetable generator, see LICENSE for details.

from django.urls import path

from plan.common import views

urlpatterns = [
    path("", views.frontpage, name="frontpage"),
    path("<semester:semester>/", views.getting_started, name="semester"),
    path("<semester:semester>/+", views.course_query, name="course-query"),
    path("<schedule:schedule>/", views.schedule, {"all": True}, name="schedule"),
    path(
        "<schedule:schedule>/+",
        views.schedule,
        {"advanced": True},
        name="schedule-advanced",
    ),
    path(
        "<schedule:schedule>/current/", views.schedule_current, name="schedule-current"
    ),
    path("<schedule:schedule>/<week:week>/", views.schedule, name="schedule-week"),
    path("<schedule:schedule>/change/", views.select_course, name="change-course"),
    path("<schedule:schedule>/groups/", views.select_groups, name="change-groups"),
    path("<schedule:schedule>/filter/", views.select_lectures, name="change-lectures"),
    path("c/<base58:id>", views.redirect, {"type": "course"}, name="redirect_course"),
    path(
        "s/<base58:id>", views.redirect, {"type": "syllabus"}, name="redirect_syllabus"
    ),
    path("r/<base58:id>", views.redirect, {"type": "room"}, name="redirect_room"),
    path("u/<base58:id>", views.redirect, {"type": "stream"}, name="redirect_stream"),
    path("+", views.about, name="about"),
    path("<student:slug>", views.shortcut, name="shortcut"),
]
