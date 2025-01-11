# This file is part of the plan timetable generator, see LICENSE for details.

from plan.common.utils import url_helper
from plan.common.views import *

urlpatterns = [
    url_helper(r"^$", frontpage, name="frontpage"),
    url_helper(r"^{year}/{semester}/$", getting_started, name="semester"),
    url_helper(r"^{year}/{semester}/\+$", course_query, name="course-query"),
    url_helper(
        r"^{year}/{semester}/{slug}/$", schedule, {"all": True}, name="schedule"
    ),
    url_helper(
        r"^{year}/{semester}/{slug}/\+$",
        schedule,
        {"advanced": True},
        name="schedule-advanced",
    ),
    url_helper(
        r"^{year}/{semester}/{slug}/current/$",
        schedule_current,
        name="schedule-current",
    ),
    url_helper(r"^{year}/{semester}/{slug}/{week}/$", schedule, name="schedule-week"),
    url_helper(
        r"^{year}/{semester}/{slug}/change/$", select_course, name="change-course"
    ),
    url_helper(
        r"^{year}/{semester}/{slug}/groups/$", select_groups, name="change-groups"
    ),
    url_helper(
        r"^{year}/{semester}/{slug}/filter/$", select_lectures, name="change-lectures"
    ),
    url_helper(r"^[+]$", about, name="about"),
    url_helper(r"^r/{id}/?$", room_redirect, name="room_redirect"),
    url_helper(r"^stats[+]$", api, name="api"),
    url_helper(r"^{slug}/?$", shortcut, name="shortcut"),
]
