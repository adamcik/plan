# Copyright 2008, 2009 Thomas Kongevold Adamcik
# 2009 IME Faculty Norwegian University of Science and Technology

# This file is part of Plan.
#
# Plan is free software: you can redistribute it and/or modify
# it under the terms of the Affero GNU General Public License as 
# published by the Free Software Foundation, either version 3 of
# the License, or (at your option) any later version.
#
# Plan is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# Affero GNU General Public License for more details.
#
# You should have received a copy of the Affero GNU General Public
# License along with Plan.  If not, see <http://www.gnu.org/licenses/>.

from django.conf.urls.defaults import *

urlpatterns = patterns('plan.common.views',
    url(r'^$', 'getting_started', name='frontpage'),
    url(r'^(?P<year>\d{4})/(?P<semester_type>\w+)/$', 'getting_started', name='frontpage-semester'),

    url(r'^(?P<year>\d{4})/(?P<semester_type>\w+)/\+$', 'course_query', name='course-query'),

    url(r'^(?P<year>\d{4})/(?P<semester_type>\w+)/(?P<slug>[a-z0-9-_]+)/$', 'schedule', {'all': True}, name='schedule'),
    url(r'^(?P<year>\d{4})/(?P<semester_type>\w+)/(?P<slug>[a-z0-9-_]+)/\+$', 'schedule', {'advanced': True}, name='schedule-advanced'),
    url(r'^(?P<year>\d{4})/(?P<semester_type>\w+)/(?P<slug>[a-z0-9-_]+)/current/$', 'schedule_current', name='schedule-current'),
    url(r'^(?P<year>\d{4})/(?P<semester_type>\w+)/(?P<slug>[a-z0-9-_]+)/(?P<week>\d{1,2})/$', 'schedule', name='schedule-week'),

    url(r'^(?P<year>\d{4})/(?P<semester_type>\w+)/(?P<slug>[a-z0-9-_]+)/list/$', 'list_courses', name='course-list'),

    url(r'^(?P<year>\d{4})/(?P<semester_type>\w+)/(?P<slug>[a-z0-9-_]+)/change/$', 'select_course', name='change-course'),
    url(r'^(?P<year>\d{4})/(?P<semester_type>\w+)/(?P<slug>[a-z0-9-_]+)/groups/$', 'select_groups', name='change-groups'),
    url(r'^(?P<year>\d{4})/(?P<semester_type>\w+)/(?P<slug>[a-z0-9-_]+)/filter/$', 'select_lectures', name='change-lectures'),

    url(r'^(?P<year>\d{4})/(?P<semester_type>\w+)/(?P<slug>[a-z0-9-_]+)/deadlines/$', 'new_deadline', name='new-deadline'),
    url(r'^(?P<year>\d{4})/(?P<semester_type>\w+)/(?P<slug>[a-z0-9-_]+)/deadlines/copy/$', 'copy_deadlines', name='copy-deadlines'),

    url(r'^(?P<slug>[a-z0-9-_]+)/$', 'shortcut', name='shortcut'),
)
