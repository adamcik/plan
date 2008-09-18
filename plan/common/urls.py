from django.conf.urls.defaults import *

urlpatterns = patterns('plan.common.views',
    url(r'^$', 'getting_started', name='frontpage'),
    url(r'^(?P<year>\d{4})/(?P<semester>\w+)/(?P<slug>[a-zA-Z0-9-_]+)/$', 'schedule', name='schedule'),
    url(r'^(?P<year>\d{4})/(?P<semester>\w+)/(?P<slug>[a-zA-Z0-9-_]+)/\+$', 'schedule', {'advanced': True}, name='schedule-advanced'),
    url(r'^(?P<year>\d{4})/(?P<semester>\w+)/(?P<slug>[a-zA-Z0-9-_]+)/(?P<week>\d{1,2})/$', 'schedule', name='schedule-week'),

    url(r'^(?P<year>\d{4})/(?P<semester>\w+)/(?P<slug>[a-zA-Z0-9-_]+)/list/$', 'list_courses', name='course-list'),

    url(r'^debug/$', 'scrape_list'),
    url(r'^debug/exam/$', 'scrape_exam'),
    url(r'^debug/(?P<course>[\w\d-]+)/$', 'scrape'),

    url(r'^(?P<year>\d{4})/(?P<type>\w+)/(?P<slug>[a-zA-Z0-9-_]+)/change/$', 'select_course', name='change-course'),
    url(r'^(?P<year>\d{4})/(?P<type>\w+)/(?P<slug>[a-zA-Z0-9-_]+)/groups/$', 'select_groups', name='change-groups'),
    url(r'^(?P<year>\d{4})/(?P<type>\w+)/(?P<slug>[a-zA-Z0-9-_]+)/filter/$', 'select_lectures', name='change-lectures'),

    url(r'^(?P<slug>[a-zA-Z0-9-_]+)/$', 'shortcut'),
)
