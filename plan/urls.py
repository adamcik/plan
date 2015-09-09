# This file is part of the plan timetable generator, see LICENSE for details.

from django.conf.urls import *
from django.conf import settings

from django.contrib.staticfiles.urls import staticfiles_urlpatterns

handler500 = 'plan.common.utils.server_error'

if settings.DEBUG:
    from django.views.generic.base import TemplateView
    urlpatterns = patterns('',
        url(r'^500/$', TemplateView.as_view(template_name='500.html')),
        url(r'^404/$', TemplateView.as_view(template_name='404.html')),
    )
else:
    urlpatterns = patterns('')

urlpatterns += patterns('',
    (r'^', include('plan.common.urls')),
    (r'^', include('plan.ical.urls')),
    (r'^', include('plan.pdf.urls')),
)

# This will only be active when DEBUG=False or --insecure is set
urlpatterns += staticfiles_urlpatterns()
