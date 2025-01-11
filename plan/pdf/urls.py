# This file is part of the plan timetable generator, see LICENSE for details.

from plan.common.utils import url_helper
from plan.pdf import views

urlpatterns = [
    url_helper(
        r"^{year}/{semester}/{slug}/pdf/(?:{size}/)?(?:{week}/)?$",
        views.pdf,
        name="schedule-pdf",
    ),
]
