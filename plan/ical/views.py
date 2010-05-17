# Copyright 2008, 2009, 2010 Thomas Kongevold Adamcik
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

import vobject

from copy import copy
from datetime import datetime, timedelta
from dateutil.rrule import rrule, WEEKLY
from dateutil.tz import tzlocal

from django.http import HttpResponse, Http404
from django.core.urlresolvers import reverse
from django.conf import settings
from django.utils.translation import ugettext as _

from plan.common.models import Exam, Deadline, Lecture, Semester, Room, Week

HOSTNAME = settings.ICAL_HOSTNAME

def get_resources(selector):
    resources = [u'lectures', u'exams', u'deadlines']

    if selector:
        parts = selector.split('+')

        for resource in copy(resources):
            if resource in parts:
                parts.remove(resource)
            else:
                resources.remove(resource)

        if parts:
            return []

    return resources

def ical(request, year, semester_type, slug, selector=None):
    resources = get_resources(selector)

    if not resources: # Invalid selectors
        raise Http404

    semester = Semester(year=year, type=semester_type)

    cache_key  = reverse('schedule-ical', args=[semester.year, semester.type, slug])
    cache_key += '+'.join(resources)

    title  = reverse('schedule', args=[semester.year, semester.type, slug])
    if len(resources) != 3:
        title += '+'.join(resources)

    response = request.cache.get(cache_key)

    if response:
        return response

    cal = vobject.iCalendar()
    cal.add('method').value = 'PUBLISH'  # IE/Outlook needs this

    if slug.lower().endswith('s'):
        description = _(u"%(slug)s' %(semester)s %(year)s schedule for %(resources)s")
    else:
        description = _(u"%(slug)s's %(semester)s %(year)s schedule for %(resources)s")

    cal.add('X-WR-CALNAME').value = title.strip('/')
    cal.add('X-WR-CALDESC').value = description % {
        'slug': slug,
        'semester': semester.get_type_display(),
        'year': semester.year,
        'resources': ', '.join(resources),
    }

    if 'lectures' in resources:
        lectures = Lecture.objects.get_lectures(year, semester.type, slug)
        add_lectutures(lectures, semester, cal)

    if 'exams' in resources:
        exams = Exam.objects.get_exams(year, semester.type, slug)
        add_exams(exams, semester, cal)

    if 'deadlines' in resources:
        deadlines = Deadline.objects.get_deadlines(year, semester.type, slug)
        add_deadlines(deadlines, semester, cal)

    icalstream = cal.serialize()

    filename = '%s.ics' % '-'.join([str(semester.year), semester.type, slug] + resources)

    response = HttpResponse(icalstream, mimetype='text/calendar')
    response['Content-Type'] = 'text/calendar; charset=utf-8'
    response['Filename'] = filename  # IE needs this
    response['Content-Disposition'] = 'attachment; filename=%s' % filename

    request.cache.set(cache_key, response)

    return response

def add_lectutures(lectures, semester, cal):
    '''Adds lectures to cal object for current semester'''

    all_rooms = Lecture.get_related(Room, lectures)
    all_weeks = Lecture.get_related(Week, lectures, fields=['number'], use_extra=False)

    for l in lectures:
        if l.exclude: # Skip excluded
            continue

        if l.id not in all_weeks:
            continue

        weeks = all_weeks[l.id]

        rrule_kwargs = {
            'byweekno': weeks,
            'count': len(weeks),
            'byweekday': l.day,
            'dtstart': datetime(int(semester.year),1,1)
        }

        summary = l.alias or l.course.code
        rooms = ', '.join(all_rooms.get(l.id, []))

        if l.type:
            desc = u'%s - %s (%s)' % (l.type.name, l.course.name, l.course.code)
        else:
            desc = u'%s (%s)' % (l.course.name, l.course.code)

        for d in rrule(WEEKLY, **rrule_kwargs):
            vevent = cal.add('vevent')
            vevent.add('summary').value = summary
            vevent.add('location').value = rooms
            vevent.add('description').value = desc

            vevent.add('dtstart').value = d.replace(hour=l.start.hour,
                    minute=l.start.minute, tzinfo=tzlocal())

            vevent.add('dtend').value = d.replace(hour=l.end.hour,
                    minute=l.end.minute, tzinfo=tzlocal())

            vevent.add('dtstamp').value = datetime.now(tzlocal())

            vevent.add('uid').value = 'lecture-%d-%s@%s' % \
                    (l.id, d.strftime('%Y%m%d'), HOSTNAME)

            if l.type and l.type.optional:
                vevent.add('transp').value = 'TRANSPARENT'

def add_exams(exams, semester, cal):
    for e in exams:

        vevent = cal.add('vevent')

        if e.type and e.type.name:
            summary = u'%s - %s' % (e.type.name, e.alias or e.course.name)
            desc = u'%s (%s) - %s (%s)' % (e.type.name, e.type.code,
                    e.course.name, e.course.code)
        elif e.type:
            summary = _('Exam') + u' (%s) - %s' % (e.type, e.alias or e.course.code)
            desc = _('Exam') + u' (%s) - %s (%s)' % (e.type.code, e.course.name,
                    e.course.code)
        else:
            summary = _('Exam') + e.alias or e.course.code
            desc = _('Exam') + u' %s (%s)' % (e.course.name, e.course.code)

        vevent.add('summary').value = summary
        vevent.add('description').value = desc
        vevent.add('dtstamp').value = datetime.now(tzlocal())

        vevent.add('uid').value = 'exam-%d@%s' % (e.id, HOSTNAME)

        if e.handout_date:
            if e.handout_time:
                vevent.add('dtstart').value = datetime.combine(e.handout_date,
                        e.handout_time).replace(tzinfo=tzlocal())
            else:
                vevent.add('dtstart').value = e.handout_date

            if e.exam_time:
                vevent.add('dtend').value = datetime.combine(e.exam_date,
                        e.exam_time).replace(tzinfo=tzlocal())
            else:
                vevent.add('dtend').value = e.exam_date
        else:
            if e.exam_time:
                start = datetime.combine(e.exam_date,
                        e.exam_time).replace(tzinfo=tzlocal())
            else:
                start = e.exam_date

            vevent.add('dtstart').value = start

            if e.duration and e.exam_time:
                vevent.add('dtend').value = start + timedelta(hours=e.duration)
            else:
                vevent.add('dtend').value = start

def add_deadlines(deadlines, semester, cal):
    for d in deadlines:
        vevent = cal.add('vevent')

        if d.time:
            start = datetime.combine(d.date, d.time)
            start = start.replace(tzinfo=tzlocal())
        else:
            start = d.date

        summary = u'%s - %s' % (d.task, d.alias or d.subscription.course)
        desc = u'%s - %s (%s)' % (d.task, d.subscription.course.name,
                d.subscription.course.code)

        vevent.add('summary').value = summary
        vevent.add('description').value = desc
        vevent.add('dtstamp').value = datetime.now(tzlocal())
        vevent.add('uid').value = 'deadline-%d@%s' % (d.id, HOSTNAME)
        vevent.add('dtstart').value = start
