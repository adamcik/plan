import vobject

from copy import copy
from socket import gethostname
from datetime import datetime, timedelta
from dateutil.rrule import rrule, WEEKLY
from dateutil.tz import tzlocal

from django.http import HttpResponse, Http404

from django.core.cache import cache

from plan.common.models import Exam, Deadline, Lecture, Semester

HOSTNAME = gethostname()

def ical(request, year, semester_type, slug, selector=None):
    resources = [u'lectures', u'exams', u'deadlines']

    if selector:
        parts = selector.split('+')

        for resource in copy(resources):
            if resource in parts:
                parts.remove(resource)
            else:
                resources.remove(resource)

        if parts: # Invalid selctors
            raise Http404

    semester = Semester(year=year, type=semester_type)

    response = cache.get(request.path)

    if response and 'plain' not in request.GET:
        return response

    cal = vobject.iCalendar()
    cal.add('method').value = 'PUBLISH'  # IE/Outlook needs this

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

    if 'plain' in request.GET:
        response = HttpResponse(icalstream)
        response['Content-Type'] = 'text/plain; charset=utf-8'
    else:
        response = HttpResponse(icalstream, mimetype='text/calendar')
        response['Content-Type'] = 'text/calendar; charset=utf-8'
        response['Filename'] = '%s.ics' % slug  # IE needs this
        response['Content-Disposition'] = 'attachment; filename=%s.ics' % slug

        cache.set(request.path, response)

    return response

def add_lectutures(lectures, semester, cal):
    '''Adds lectures to cal object for current semester'''

    for l in lectures:
        if l.exclude: # Skip excluded
            continue

        weeks = l.weeks.values_list('number', flat=True)

        rrule_kwargs = {
            'byweekno': weeks,
            'count': len(weeks),
            'byweekday': l.day,
            'dtstart': datetime(int(semester.year),1,1)
        }

        summary = l.alias or l.course.name
        # FIXME this propably causes an extra query that could easily be
        # avoided
        rooms = ', '.join(l.rooms.values_list('name', flat=True))
        desc = '%s - %s (%s)' % (l.type.name, l.course.full_name, l.course.name)

        for d in rrule(WEEKLY, **rrule_kwargs):
            vevent = cal.add('vevent')
            vevent.add('summary').value = summary
            vevent.add('location').value = rooms
            vevent.add('description').value = desc

            (hour, minute) = l.get_start_time_display().split(':')
            vevent.add('dtstart').value = d.replace(hour=int(hour),
                    minute=int(minute), tzinfo=tzlocal())

            (hour, minute) = l.get_end_time_display().split(':')
            vevent.add('dtend').value = d.replace(hour=int(hour),
                    minute=int(minute), tzinfo=tzlocal())

            vevent.add('dtstamp').value = datetime.now(tzlocal())

            vevent.add('uid').value = 'lecture-%d-%s@%s' % \
                    (l.id, d.strftime('%Y%m%d'), HOSTNAME)

            if l.type.optional:
                vevent.add('transp').value = 'TRANSPARENT'

def add_exams(exams, semester, cal):
    for e in exams:

        vevent = cal.add('vevent')

        if e.type_name:
            summary = '%s - %s' % (e.type_name, e.alias or e.course.name)
            desc = '%s (%s) - %s (%s)' % (e.type_name, e.type,
                    e.course.full_name, e.course.name)
        else:
            summary = 'Exam (%s) - %s' % (e.type, e.alias or e.course.name)
            desc = 'Exam (%s) - %s (%s)' % (e.type, e.course.full_name,
                    e.course.name)

        vevent.add('summary').value = summary
        vevent.add('description').value = desc
        vevent.add('dtstamp').value = datetime.now(tzlocal())

        vevent.add('uid').value = 'exam-%d@%s' % (e.id, HOSTNAME)

        if e.handout_time:
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

            if e.duration is None or not e.exam_time:
                duration = timedelta()
            elif e.duration == 30: # FIXME is this right?
                duration = timedelta(minutes=30)
            else:
                duration = timedelta(hours=e.duration)

            if e.duration is None:
                vevent.add('dtend').value = start
            else:
                vevent.add('dtend').value = start + duration

def add_deadlines(deadlines, semester, cal):
    for d in deadlines:
        vevent = cal.add('vevent')

        start = d.date
        if d.time:
            start = datetime.combine(d.date, d.time)

        summary = '%s - %s' % (d.task, d.alias or d.userset.course)
        desc = '%s - %s (%s)' % (d.task, d.userset.course.full_name,
                d.userset.course.name)

        vevent.add('summary').value = summary
        vevent.add('description').value = desc
        vevent.add('dtstamp').value = datetime.now(tzlocal())
        vevent.add('uid').value = 'deadline-%d@%s' % (d.id, HOSTNAME)
        vevent.add('dtstart').value = start
