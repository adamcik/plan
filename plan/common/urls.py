from django.conf.urls.defaults import *

from plan.common.models import Room, Course

urlpatterns = patterns('plan.common.views',
    url(r'^$', 'getting_started'),
    url(r'^s/(?P<slug>[a-zA-Z0-9-_]+)/$', 'schedule', name='schedule'),
    url(r'^s/(?P<slug>[a-zA-Z0-9-_]+)/(?P<year>\d{4})/(?P<semester>\w+)/$', 'schedule'),

    url(r'^debug/$', 'scrape_list'),
    url(r'^debug/(?P<course>[\w\d-]+)/$', 'scrape'),
    url(r'^s/(?P<slug>[a-zA-Z0-9-_]+)/alter/$', 'select_course', name='select_course'),
    url(r'^s/(?P<slug>[a-zA-Z0-9-_]+)/groups/$', 'select_groups', name='select_groups'),
)
