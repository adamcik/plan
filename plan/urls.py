# This file is part of the plan timetable generator, see LICENSE for details.

from django.conf.urls import *
from django.conf import settings

handler500 = 'plan.common.utils.server_error'

if settings.DEBUG:
    urlpatterns = patterns('',
        url(r'^500/$', 'django.views.generic.simple.direct_to_template', {'template': '500.html'}),
        url(r'^404/$', 'django.views.generic.simple.direct_to_template', {'template': '404.html'}),
    )
else:
    urlpatterns = patterns('')

urlpatterns += patterns('',
    (r'^', include('plan.common.urls')),
    (r'^', include('plan.ical.urls')),
    (r'^', include('plan.pdf.urls')),
)
