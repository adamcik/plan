# This file is part of the plan timetable generator, see LICENSE for details.

import copy
import datetime
import math
import socket
import vobject

from dateutil import rrule
from dateutil import tz

from django import http
from django.conf import settings
from django.core import urlresolvers
from django.utils import translation

from plan.common.models import Exam, Lecture, Semester, Room, Week

_ = translation.ugettext


def ical(request, year, semester_type, slug, ical_type=None):
    resources = [_(u'lectures'), _(u'exams')]
    if ical_type and ical_type not in resources:
        raise http.Http404
    elif ical_type:
        resources = [ical_type]

    title  = urlresolvers.reverse('schedule', args=[year, semester_type, slug])
    hostname = (settings.TIMETABLE_HOSTNAME or
                request.META.get('HTTP_HOST', socket.getfqdn()))

    semester = Semester(year=year, type=semester_type)

    cal = vobject.iCalendar()
    cal.add('method').value = 'PUBLISH'  # IE/Outlook needs this

    # TODO(adamcik): use same logic as in common.templatetags.title
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

    if _('lectures') in resources:
        lectures = Lecture.objects.get_lectures(year, semester.type, slug)
        add_lectutures(lectures, semester.year, cal, hostname)

    if _('exams') in resources:
        exams = Exam.objects.get_exams(year, semester.type, slug)
        add_exams(exams, cal, hostname)

    icalstream = cal.serialize()

    filename = '%s.ics' % '-'.join([str(semester.year), semester.type, slug] + resources)

    response = http.HttpResponse(icalstream, content_type='text/calendar')
    response['Content-Type'] = 'text/calendar; charset=utf-8'
    response['Filename'] = filename  # IE needs this
    response['Content-Disposition'] = 'attachment; filename=%s' % filename
    response['X-Robots-Tag'] = 'noindex, nofollow'

    # TODO(adamcik): add expires header that reduces load on old semesters

    return response


def add_lectutures(lectures, year, cal, hostname):
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
            'dtstart': datetime.datetime(int(year),1,1)
        }

        summary = l.alias or l.course.code
        rooms = ', '.join(all_rooms.get(l.id, []))

        if l.type:
            desc = u'%s - %s (%s)' % (l.type.name, l.course.name, l.course.code)
        else:
            desc = u'%s (%s)' % (l.course.name, l.course.code)

        for d in rrule.rrule(rrule.WEEKLY, **rrule_kwargs):
            vevent = cal.add('vevent')
            vevent.add('summary').value = summary
            vevent.add('location').value = rooms
            vevent.add('description').value = desc

            vevent.add('dtstart').value = d.replace(hour=l.start.hour,
                    minute=l.start.minute, tzinfo=tz.tzlocal())

            vevent.add('dtend').value = d.replace(hour=l.end.hour,
                    minute=l.end.minute, tzinfo=tz.tzlocal())

            vevent.add('dtstamp').value = datetime.datetime.now(tz.tzlocal())

            vevent.add('uid').value = 'lecture-%d-%s@%s' % \
                    (l.id, d.strftime('%Y%m%d'), hostname)

            if l.type and l.type.optional:
                vevent.add('transp').value = 'TRANSPARENT'


def add_exams(exams, cal, hostname):
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
            summary = _('Exam') + u' %s' % (e.alias or e.course.code)
            desc = _('Exam') + u' %s (%s)' % (e.course.name, e.course.code)

        vevent.add('summary').value = summary
        vevent.add('description').value = desc
        vevent.add('dtstamp').value = datetime.datetime.now(tz.tzlocal())

        vevent.add('uid').value = 'exam-%d@%s' % (e.id, hostname)

        if e.handout_date:
            if e.handout_time:
                vevent.add('dtstart').value = datetime.datetime.combine(
                    e.handout_date, e.handout_time).replace(tzinfo=tz.tzlocal())
            else:
                vevent.add('dtstart').value = e.handout_date

            if e.exam_time:
                vevent.add('dtend').value = datetime.datetime.combine(
                    e.exam_date, e.exam_time).replace(tzinfo=tz.tzlocal())
            else:
                vevent.add('dtend').value = e.exam_date
        else:
            if e.exam_time:
                start = datetime.datetime.combine(
                    e.exam_date, e.exam_time).replace(tzinfo=tz.tzlocal())
            else:
                start = e.exam_date

            vevent.add('dtstart').value = start

            if e.duration and e.exam_time:
                hours = int(math.floor(e.duration))
                minutes = int((e.duration % 1) * 60)
                vevent.add('dtend').value = start + datetime.timedelta(
                    hours=hours, minutes=minutes)
            else:
                vevent.add('dtend').value = start
