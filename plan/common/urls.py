from django.conf.urls.defaults import *

urlpatterns = patterns('plan.common.views',
    url(r'^$', 'getting_started', name='frontpage'),
    url(r'^(?P<year>\d{4})/(?P<semester>\w+)/(?P<slug>[a-zA-Z0-9-_]+)/$', 'schedule', name='schedule'),
    url(r'^(?P<year>\d{4})/(?P<semester>\w+)/(?P<slug>[a-zA-Z0-9-_]+)/\+$', 'schedule', {'advanced': True}, name='schedule-advanced'),

    url(r'^debug/$', 'scrape_list'),
    url(r'^debug/exam/$', 'scrape_exam'),
    url(r'^debug/(?P<course>[\w\d-]+)/$', 'scrape'),

    url(r'^s/(?P<slug>[a-zA-Z0-9-_]+)/alter/$', 'select_course', name='select_course'),
    url(r'^s/(?P<slug>[a-zA-Z0-9-_]+)/groups/$', 'select_groups', name='select_groups'),
    url(r'^s/(?P<slug>[a-zA-Z0-9-_]+)/exclude/$', 'select_lectures', name='select_lectures'),

    url(r'^(?P<year>\d{4})/(?P<type>\w+)/(?P<slug>[a-zA-Z0-9-_]+)/change/$', 'select_course', name='change-course'),
    url(r'^(?P<year>\d{4})/(?P<type>\w+)/(?P<slug>[a-zA-Z0-9-_]+)/groups/$', 'select_groups', name='change-groups'),
    url(r'^(?P<year>\d{4})/(?P<type>\w+)/(?P<slug>[a-zA-Z0-9-_]+)/exclude/$', 'select_lectures', name='change-lectures'),
)
