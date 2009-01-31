from django.conf.urls.defaults import *

urlpatterns = patterns('plan.ical.views',
    url(r'^(?P<year>\d{4})/(?P<semester_type>\w+)/(?P<slug>[a-z0-9-_]+)/ical/(?:(?P<selector>\w+[+\w]*)/)?$', 'ical', name='schedule-ical'),
)
