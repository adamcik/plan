# This file is part of the plan timetable generator, see LICENSE for details.

from plan.common.utils import url_helper
from plan.ical import views

urlpatterns = [
    url_helper(
        r"^{year}/{semester}/{slug}/ical/(?:{ical}/)?$",
        views.ical,
        name="schedule-ical",
    ),
]
