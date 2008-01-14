from django.conf.urls.defaults import *

urlpatterns = patterns('',
    # Example:
    # (r'^plan/', include('plan.foo.urls')),

    (r'^admin/', include('django.contrib.admin.urls')),
)
