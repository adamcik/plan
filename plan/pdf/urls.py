# This file is part of the plan timetable generator, see LICENSE for details.

from django.conf.urls import patterns
from plan.common.utils import url

urlpatterns = patterns('plan.pdf.views',
    url(r'^{year}/{semester}/{slug}/pdf/(?:{size}/)?(?:{week}/)?$', 'pdf', name='schedule-pdf'),
)
