# This file is part of the plan timetable generator, see LICENSE for details.

from django.conf.urls.defaults import patterns, url

urlpatterns = patterns('plan.ical.views',
    url(r'^(?P<year>\d{4})/(?P<semester_type>\w+)/(?P<slug>[a-z0-9-_]{1,50})/ical/(?:(?P<selector>\w+[+\w]*)/)?$', 'ical', name='schedule-ical'),
)
