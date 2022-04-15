# This file is part of the plan timetable generator, see LICENSE for details.

from __future__ import absolute_import
from plan.common.utils import url
from plan.ical import views

urlpatterns = [
    url(r'^{year}/{semester}/{slug}/ical/(?:{ical}/)?$', views.ical, name='schedule-ical'),
]
