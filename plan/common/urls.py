# This file is part of the plan timetable generator, see LICENSE for details.

from django.conf.urls import patterns
from plan.common.utils import url

urlpatterns = patterns('plan.common.views',
    url(r'^$', 'frontpage', name='frontpage'),
    url(r'^{year}/{semester}/$', 'getting_started', name='semester'),

    url(r'^{year}/{semester}/\+$', 'course_query', name='course-query'),

    url(r'^{year}/{semester}/{slug}/$', 'schedule', {'all': True}, name='schedule'),
    url(r'^{year}/{semester}/{slug}/\+$', 'schedule', {'advanced': True}, name='schedule-advanced'),
    url(r'^{year}/{semester}/{slug}/current/$', 'schedule_current', name='schedule-current'),
    url(r'^{year}/{semester}/{slug}/{week}/$', 'schedule', name='schedule-week'),

    url(r'^{year}/{semester}/{slug}/list/$', 'list_courses', name='course-list'),

    url(r'^{year}/{semester}/{slug}/change/$', 'select_course', name='change-course'),
    url(r'^{year}/{semester}/{slug}/groups/$', 'select_groups', name='change-groups'),
    url(r'^{year}/{semester}/{slug}/filter/$', 'select_lectures', name='change-lectures'),

    url(r'^{year}/{semester}/{slug}/deadlines/$', 'new_deadline', name='new-deadline'),
    url(r'^{year}/{semester}/{slug}/deadlines/copy/$', 'copy_deadlines', name='copy-deadlines'),

    url(r'^{year}/{semester}/{slug}/deadlines/toggle/$', 'toggle_deadlines', name='toggle-deadlines'),

    url(r'^about/$', 'about', name='about'),
    url(r'^{slug}/$', 'shortcut', name='shortcut'),
)
