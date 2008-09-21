from django.conf.urls.defaults import *

exams = {'exams': True, 'lectures': False, 'deadlines': False}
lectures = {'exams': False, 'lectures': True, 'deadlines': False}
deadlines = {'exams': False, 'lectures': False, 'deadlines': True}


urlpatterns = patterns('plan.ical.views',
    url(r'^(?P<year>\d{4})/(?P<semester>\w+)/(?P<slug>[a-zA-Z0-9-_]+)/ical/$', 'ical', name='schedule-ical'),
    url(r'^(?P<year>\d{4})/(?P<semester>\w+)/(?P<slug>[a-zA-Z0-9-_]+)/ical/exams/$', 'ical', exams, name='schedule-ical-exams'),
    url(r'^(?P<year>\d{4})/(?P<semester>\w+)/(?P<slug>[a-zA-Z0-9-_]+)/ical/lectures/$', 'ical', lectures, name='schedule-ical-lectures'),
    url(r'^(?P<year>\d{4})/(?P<semester>\w+)/(?P<slug>[a-zA-Z0-9-_]+)/ical/deadlines/$', 'ical', deadlines, name='schedule-ical-deadlines'),
)
