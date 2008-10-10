import vobject

from socket import gethostname
from datetime import datetime, timedelta
from dateutil.rrule import *
from dateutil.parser import parse
from dateutil.tz import tzlocal

from django.http import HttpResponse

from django.core.cache import cache

from plan.common.models import *
from plan.common.views import get_semester, get_lectures

def ical(request, year, semester, slug, lectures=True, exams=True, deadlines=True):
    semester = get_semester(year, semester)

    # FIXME cache the response! use request path..
    response = cache.get(request.path)

    if response and 'plain' not in request.GET:
        return response

    cal = vobject.iCalendar()
    cal.add('method').value = 'PUBLISH'  # IE/Outlook needs this

    if lectures:
        add_lectutures(get_lectures(slug, semester).exclude(excluded_from__slug=slug), semester, cal)

    if exams:
        add_exams(slug, semester, cal)

    if deadlines:
        add_deadlines(slug, semester, cal)

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
        weeks = l.weeks.values_list('number', flat=True)

        rrule_kwargs = {
            'byweekno': weeks,
            'count': len(weeks),
            'byweekday': l.day,
            'dtstart': datetime(int(semester.year),1,1)
        }

        summary = l.user_name or l.course.name
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
                    (l.id, d.strftime('%Y%m%d'), gethostname())

            if l.type.optional:
                vevent.add('transp').value = 'TRANSPARENT'

def add_exams(slug, semester, cal):
    first_day = semester.get_first_day()
    last_day = semester.get_last_day()

    exam_filter = {
        'exam_date__gt': first_day,
        'exam_date__lt': last_day,
        'course__userset__slug': slug,
    }
    exam_related = [
        'course__name',
        'course__full_name',
    ]
    exam_select = {
        'user_name': 'common_userset.name',
    }

    for e in Exam.objects.filter(**exam_filter).select_related(*exam_related).\
            extra(select=exam_select):

        vevent = cal.add('vevent')

        if e.type_name:
            summary = '%s - %s' % (e.type_name, e.user_name or e.course.name)
            desc = '%s (%s) - %s (%s)' % (e.type_name, e.type, e.course.full_name, e.course.name)
        else:
            summary = 'Exam (%s) - %s' % (e.type, e.user_name or e.course.name)
            desc = 'Exam (%s) - %s (%s)' % (e.type, e.course.full_name, e.course.name)

        vevent.add('summary').value = summary
        vevent.add('description').value = desc
        vevent.add('dtstamp').value = datetime.now(tzlocal())

        vevent.add('uid').value = 'exam-%d@%s' % (e.id, gethostname())

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
                pass
            elif e.duration == 30:
                duration = timedelta(minutes=30)
            else:
                duration = timedelta(hours=e.duration)

            if e.duration is None:
                vevent.add('dtend').value = start
            else:
                vevent.add('dtend').value = start + duration

def add_deadlines(slug, semester, cal):
    deadline_filter = {
        'userset__slug': slug,
        'userset__semester': semester,
    }
    deadline_related = [
        'userset__course__name',
        'userset__course__full_name',
    ]
    deadline_select = {
        'user_name': 'common_userset.name',
    }

    for d in Deadline.objects.filter(**deadline_filter).\
            select_related(*deadline_related).extra(select=deadline_select):

        vevent = cal.add('vevent')

        start = d.date
        if d.time:
            start = datetime.combine(d.date, d.time)

        summary = '%s - %s' % (d.task, d.user_name or d.userset.course)
        desc = '%s - %s (%s)' % (d.task, d.userset.course.full_name,
                d.userset.course.name)

        vevent.add('summary').value = summary
        vevent.add('description').value = desc
        vevent.add('dtstamp').value = datetime.now(tzlocal())
        vevent.add('uid').value = 'deadline-%d@%s' % (d.id, gethostname())
        vevent.add('dtstart').value = start

