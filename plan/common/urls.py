# This file is part of the plan timetable generator, see LICENSE for details.

from django.conf.urls.defaults import patterns, url

urlpatterns = patterns('plan.common.views',
    url(r'^$', 'frontpage', name='frontpage'),
    url(r'^(?P<year>\d{4})/(?P<semester_type>\w+)/$', 'getting_started', name='semester'),

    url(r'^(?P<year>\d{4})/(?P<semester_type>\w+)/\+$', 'course_query', name='course-query'),

    url(r'^(?P<year>\d{4})/(?P<semester_type>\w+)/(?P<slug>[a-z0-9-_]{1,50})/$', 'schedule', {'all': True}, name='schedule'),
    url(r'^(?P<year>\d{4})/(?P<semester_type>\w+)/(?P<slug>[a-z0-9-_]{1,50})/\+$', 'schedule', {'advanced': True}, name='schedule-advanced'),
    url(r'^(?P<year>\d{4})/(?P<semester_type>\w+)/(?P<slug>[a-z0-9-_]{1,50})/current/$', 'schedule_current', name='schedule-current'),
    url(r'^(?P<year>\d{4})/(?P<semester_type>\w+)/(?P<slug>[a-z0-9-_]{1,50})/(?P<week>\d{1,2})/$', 'schedule', name='schedule-week'),

    url(r'^(?P<year>\d{4})/(?P<semester_type>\w+)/(?P<slug>[a-z0-9-_]{1,50})/list/$', 'list_courses', name='course-list'),

    url(r'^(?P<year>\d{4})/(?P<semester_type>\w+)/(?P<slug>[a-z0-9-_]{1,50})/change/$', 'select_course', name='change-course'),
    url(r'^(?P<year>\d{4})/(?P<semester_type>\w+)/(?P<slug>[a-z0-9-_]{1,50})/groups/$', 'select_groups', name='change-groups'),
    url(r'^(?P<year>\d{4})/(?P<semester_type>\w+)/(?P<slug>[a-z0-9-_]{1,50})/filter/$', 'select_lectures', name='change-lectures'),

    url(r'^(?P<year>\d{4})/(?P<semester_type>\w+)/(?P<slug>[a-z0-9-_]{1,50})/deadlines/$', 'new_deadline', name='new-deadline'),
    url(r'^(?P<year>\d{4})/(?P<semester_type>\w+)/(?P<slug>[a-z0-9-_]{1,50})/deadlines/copy/$', 'copy_deadlines', name='copy-deadlines'),

    url(r'^(?P<year>\d{4})/(?P<semester_type>\w+)/(?P<slug>[a-z0-9-_]{1,50})/deadlines/toggle/$', 'toggle_deadlines', name='toggle-deadlines'),

    url(r'^about/$', 'about', name='about'),
    url(r'^(?P<slug>[a-z0-9-_]{1,50})/$', 'shortcut', name='shortcut'),
)
