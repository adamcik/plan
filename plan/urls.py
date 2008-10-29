from django.conf.urls.defaults import *
from django.conf import settings
from django.contrib import databrowse

from plan.common.models import Course, Group, Lecture, Lecturer, Room, \
        Semester, Type, Exam

from plan.common.admin import admin

databrowse.site.register(Course)
databrowse.site.register(Group)
databrowse.site.register(Lecture)
databrowse.site.register(Lecturer)
databrowse.site.register(Room)
databrowse.site.register(Semester)
databrowse.site.register(Type)
databrowse.site.register(Exam)

handler500 = 'plan.common.utils.server_error'

if settings.DEBUG:
    urlpatterns = patterns('',
        url(r"%s(?P<path>.*)$" % settings.MEDIA_URL[1:], 'django.views.static.serve', {'document_root': settings.MEDIA_ROOT}),
        url(r'^500/$', 'django.views.generic.simple.direct_to_template', {'template': '500.html'}),
        url(r'^404/$', 'django.views.generic.simple.direct_to_template', {'template': '404.html'}),
    )
else:
    urlpatterns = patterns()

urlpatterns += patterns('',
    (r'^admin/(.*)', admin.site.root),
    (r'^data/(.*)', databrowse.site.root),

    (r'^', include('plan.common.urls')),
    (r'^', include('plan.ical.urls')),
    (r'^', include('plan.pdf.urls')),
)

