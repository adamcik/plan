# This file is part of the plan timetable generator, see LICENSE for details.

from plan.common import views
from plan.common.utils import url_helper

urlpatterns = [
    url_helper(r"^$", views.frontpage, name="frontpage"),
    url_helper(r"^{year}/{semester}/$", views.getting_started, name="semester"),
    url_helper(r"^{year}/{semester}/\+$", views.course_query, name="course-query"),
    url_helper(
        r"^{year}/{semester}/{slug}/$", views.schedule, {"all": True}, name="schedule"
    ),
    url_helper(
        r"^{year}/{semester}/{slug}/\+$",
        views.schedule,
        {"advanced": True},
        name="schedule-advanced",
    ),
    url_helper(
        r"^{year}/{semester}/{slug}/current/$",
        views.schedule_current,
        name="schedule-current",
    ),
    url_helper(
        r"^{year}/{semester}/{slug}/{week}/$", views.schedule, name="schedule-week"
    ),
    url_helper(
        r"^{year}/{semester}/{slug}/change/$", views.select_course, name="change-course"
    ),
    url_helper(
        r"^{year}/{semester}/{slug}/groups/$", views.select_groups, name="change-groups"
    ),
    url_helper(
        r"^{year}/{semester}/{slug}/filter/$",
        views.select_lectures,
        name="change-lectures",
    ),
    url_helper(r"^[+]$", views.about, name="about"),
    # TODO: consider converter for base58 for id?
    url_helper(
        r"^course/{id}/?$", views.redirect, {"type": "course"}, name="redirect_course"
    ),
    url_helper(
        r"^syllabus/{id}/?$",
        views.redirect,
        {"type": "syllabus"},
        name="redirect_syllabus",
    ),
    url_helper(
        r"^room/{id}/?$", views.redirect, {"type": "room"}, name="redirect_room"
    ),
    url_helper(
        r"^stream/{id}/?$", views.redirect, {"type": "stream"}, name="redirect_stream"
    ),
    url_helper(r"^stats[+]$", views.api, name="api"),
    url_helper(r"^{slug}/?$", views.shortcut, name="shortcut"),
]
