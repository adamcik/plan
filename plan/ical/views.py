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

def ical(request, year, semester, slug, lectures=True, exams=True):
    semester = get_semester(year, semester)

    # FIXME cache the response! use request path..
    response = cache.get(request.path)

    if response and 'plain' not in request.GET:
        return response

    cal = vobject.iCalendar()
    cal.add('method').value = 'PUBLISH'  # IE/Outlook needs this

    if lectures:
        for l in get_lectures(slug, semester).exclude(excluded_from__slug=slug):
            weeks = l.weeks.values_list('number', flat=True)

            for d in rrule(WEEKLY,byweekno=weeks,count=len(weeks),byweekday=l.day,dtstart=datetime(int(year),1,1)):
                vevent = cal.add('vevent')
                vevent.add('summary').value = l.course.name
                vevent.add('location').value = ', '.join(l.rooms.values_list('name', flat=True))
                vevent.add('description').value = '%s - %s' % (l.type.name, l.course.full_name)

                (hour, minute) = l.get_start_time_display().split(':')
                vevent.add('dtstart').value = d.replace(hour=int(hour), minute=int(minute), tzinfo=tzlocal())

                (hour, minute) = l.get_end_time_display().split(':')
                vevent.add('dtend').value = d.replace(hour=int(hour), minute=int(minute), tzinfo=tzlocal())

                vevent.add('dtstamp').value = datetime.now(tzlocal())

                vevent.add('uid').value = 'lecture-%d-%s@%s' % (l.id, d.strftime('%Y%m%d'), gethostname())

                if l.type.optional:
                    vevent.add('transp').value = 'TRANSPARENT'


    if exams:
        first_day = semester.get_first_day()
        last_day = semester.get_last_day()

        for e in Exam.objects.filter(exam_date__gt=first_day, exam_date__lt=last_day, course__userset__slug=slug).select_related('course__name'):
            vevent = cal.add('vevent')

            vevent.add('summary').value = 'Exam: %s (%s)' % (e.course.name, e.type)
            vevent.add('description').value = 'Exam (%s) - %s' % (e.type, e.course.full_name)
            vevent.add('dtstamp').value = datetime.now(tzlocal())

            vevent.add('uid').value = 'exam-%d@%s' % (e.id, gethostname())

            if e.handout_time:
                if e.handout_time:
                    vevent.add('dtstart').value = datetime.combine(e.handout_date, e.handout_time).replace(tzinfo=tzlocal())
                else:
                    vevent.add('dtstart').value = e.handout_date

                if e.exam_time:
                    vevent.add('dtend').value = datetime.combine(e.exam_date, e.exam_time).replace(tzinfo=tzlocal())
                else:
                    vevent.add('dtend').value = e.exam_date
            else:
                if e.exam_time:
                    start = datetime.combine(e.exam_date, e.exam_time).replace(tzinfo=tzlocal())
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

    icalstream = cal.serialize()

    if 'plain' in request.GET:
        response = HttpResponse(icalstream, mimetype='text/plain')
    else:
        response = HttpResponse(icalstream, mimetype='text/calendar')
        response['Filename'] = '%s.ics' % slug  # IE needs this
        response['Content-Disposition'] = 'attachment; filename=%s.ics' % slug
        cache.set(request.path, response)

    return response

