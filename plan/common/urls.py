# This file is part of the plan timetable generator, see LICENSE for details.

from plan.common.utils import url
from plan.common.views import *

urlpatterns = [
    url(r"^$", frontpage, name="frontpage"),
    url(r"^{year}/{semester}/$", getting_started, name="semester"),
    url(r"^{year}/{semester}/\+$", course_query, name="course-query"),
    url(r"^{year}/{semester}/{slug}/$", schedule, {"all": True}, name="schedule"),
    url(
        r"^{year}/{semester}/{slug}/\+$",
        schedule,
        {"advanced": True},
        name="schedule-advanced",
    ),
    url(
        r"^{year}/{semester}/{slug}/current/$",
        schedule_current,
        name="schedule-current",
    ),
    url(r"^{year}/{semester}/{slug}/{week}/$", schedule, name="schedule-week"),
    url(r"^{year}/{semester}/{slug}/change/$", select_course, name="change-course"),
    url(r"^{year}/{semester}/{slug}/groups/$", select_groups, name="change-groups"),
    url(r"^{year}/{semester}/{slug}/filter/$", select_lectures, name="change-lectures"),
    url(r"^[+]$", about, name="about"),
    url(r"^r/{id}/?$", room_redirect, name="room_redirect"),
    url(r"^{slug}/?$", shortcut, name="shortcut"),
]
