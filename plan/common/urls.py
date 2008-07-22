from django.conf.urls.defaults import *

urlpatterns = patterns('plan.common.views',
    url(r'^$', 'list'),
    url(r'^s/(?P<slug>[a-zA-Z0-9-_]+)/$', 'schedule'),
    url(r'^s/(?P<slug>[a-zA-Z0-9-_]+)/(?P<year>\d{4})/(?P<semester>\w+)/$', 'schedule'),
)
