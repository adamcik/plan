# This file is part of the plan timetable generator, see LICENSE for details.

from django.urls import path

from plan.common import views

urlpatterns = [
    path(
        "",
        views.frontpage,
        name="frontpage",
    ),
    path(
        "<int:year>/<str:semester_type>/",
        views.getting_started,
        name="semester",
    ),
    path(
        "<int:year>/<str:semester_type>/+",
        views.course_query,
        name="course-query",
    ),
    path(
        "<int:year>/<str:semester_type>/<slug:slug>/+",
        views.schedule,
        {"all": True},
        name="schedule",
    ),
    path(
        "<int:year>/<str:semester_type>/<slug:slug>/+",
        views.schedule,
        {"advanced": True},
        name="schedule-advanced",
    ),
    path(
        "<int:year>/<str:semester_type>/<slug:slug>/current/",
        views.schedule_current,
        name="schedule-current",
    ),
    path(
        "<int:year>/<str:semester_type>/<slug:slug>/<int:week>/",
        views.schedule,
        name="schedule-week",
    ),
    path(
        "<int:year>/<str:semester_type>/<slug:slug>/change/",
        views.select_course,
        name="change-course",
    ),
    path(
        "<int:year>/<str:semester_type>/<slug:slug>/groups/",
        views.select_groups,
        name="change-groups",
    ),
    path(
        "<int:year>/<str:semester_type>/<slug:slug>/filter/",
        views.select_lectures,
        name="change-lectures",
    ),
    path(
        "+",
        views.about,
        name="about",
    ),
    # TODO: consider converter for base58 for id?
    path(
        "course/<int:id>/",
        views.redirect,
        {"type": "course"},
        name="redirect_course",
    ),
    path(
        "syllabus/<int:id>/",
        views.redirect,
        {"type": "syllabus"},
        name="redirect_syllabus",
    ),
    path(
        "room/<int:id>/",
        views.redirect,
        {"type": "room"},
        name="redirect_room",
    ),
    path(
        "stream/<int:id>/",
        views.redirect,
        {"type": "stream"},
        name="redirect_stream",
    ),
    path(
        "<slug:slug>",
        views.shortcut,
        name="shortcut",
    ),
]
