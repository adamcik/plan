# This file is part of the plan timetable generator, see LICENSE for details.

from django.conf.urls.defaults import *
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
    (r'^i18n/', include('django.conf.urls.i18n')),

    (r'^', include('plan.common.urls')),
    (r'^', include('plan.ical.urls')),
    (r'^', include('plan.pdf.urls')),

)

