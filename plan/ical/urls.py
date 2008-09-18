from django.conf.urls.defaults import *

urlpatterns = patterns('plan.ical.views',
    url(r'^(?P<year>\d{4})/(?P<semester>\w+)/(?P<slug>[a-zA-Z0-9-_]+)/ical/$', 'ical', name='schedule-ical'),
    url(r'^(?P<year>\d{4})/(?P<semester>\w+)/(?P<slug>[a-zA-Z0-9-_]+)/ical/exams/$', 'ical', {'exams': True, 'lectures': False}, name='schedule-ical-exams'),
    url(r'^(?P<year>\d{4})/(?P<semester>\w+)/(?P<slug>[a-zA-Z0-9-_]+)/ical/lectures/$', 'ical', {'exams': False, 'lectures': True}, name='schedule-ical-lectures'),
)
