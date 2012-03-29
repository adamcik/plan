# This file is part of the plan timetable generator, see LICENSE for details.

from django.conf.urls.defaults import *

urlpatterns = patterns('plan.pdf.views',
    url(r'^(?P<year>\d{4})/(?P<semester_type>\w+)/(?P<slug>[a-z0-9-_]{1,50})/pdf/(?:(?P<size>A\d)/)?(?:(?P<week>\d+)/)?$', 'pdf', name='schedule-pdf'),
)
