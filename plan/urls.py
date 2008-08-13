from django.conf.urls.defaults import *
from django.conf import settings
from django.contrib import admin
from django.contrib import databrowse

from plan.common.models import *

admin.autodiscover()

databrowse.site.register(Course)
databrowse.site.register(Group)
databrowse.site.register(Lecture)
databrowse.site.register(Lecturer)
databrowse.site.register(Room)
databrowse.site.register(Semester)
databrowse.site.register(Type)
databrowse.site.register(Exam)

handler500 = 'plan.common.utils.server_error'

urlpatterns = patterns('',
    (r'^admin/(.*)', admin.site.root),
    (r'^data/(.*)', databrowse.site.root),

    (r'^', include('plan.common.urls')),

    url(r'^media/(?P<path>.*)$', 'django.views.static.serve', {'document_root': settings.MEDIA_ROOT}, name='media'),
)
