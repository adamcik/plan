# This file is part of the plan timetable generator, see LICENSE for details.

from django.conf.urls import patterns
from plan.common.utils import url

urlpatterns = patterns('plan.ical.views',
    url(r'^{year}/{semester}/{slug}/ical/(?:{ical}/)?$', 'ical', name='schedule-ical'),
)
