from django.conf.urls.defaults import *

from plan.common.models import Room, Course

urlpatterns = patterns('plan.common.views',
    url(r'^$', 'list'),

    url(r'^s/(?P<slug>[a-zA-Z0-9-_]+)/$', 'schedule'),
    url(r'^s/(?P<slug>[a-zA-Z0-9-_]+)/(?P<year>\d{4})/(?P<semester>\w+)/$', 'schedule'),

    url(r'^r/$', 'add_many', {'model': Room}, name='add_rooms'),
    url(r'^c/$', 'add_many', {'model': Course}, name='add_courses'),

    url(r'^l/(?P<course>[\w\d-]+)/$', 'scrape'),
)
