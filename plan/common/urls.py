from django.conf.urls.defaults import *

from plan.common.views import *

urlpatterns = patterns('',
    url(r'^(?P<slug>[a-zA-Z0-9-_]+)/$', schedule),
)
