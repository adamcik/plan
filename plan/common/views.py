# encoding: utf-8

import logging
import vobject
import traceback
import sys

from socket import gethostname
from datetime import datetime, timedelta
from dateutil.rrule import *
from dateutil.parser import parse
from dateutil.tz import tzlocal

from django.core.urlresolvers import reverse, NoReverseMatch
from django.db.models import Q
from django.http import HttpResponseRedirect, HttpResponse, Http404
from django.shortcuts import get_object_or_404, render_to_response
from django.template.context import RequestContext
from django.template.defaultfilters import slugify
from django.views.decorators.cache import cache_page
from django.core.cache import cache
from django.db import connection
from django.views.generic.list_detail import object_list
from django.core import serializers

from plan.common.models import *
from plan.common.forms import *
from plan.common.utils import *
from plan.scrape.web import *

MAX_COLORS = 8

def get_semester(year, semester):
    try:
        semester = dict(map(lambda x: (x[1],x[0]), Semester.TYPES))[semester.lower()]
        return Semester.objects.get(year=year, type=semester)
    except (KeyError, Semester.DoesNotExist):
        raise Http404

def get_lectures(slug, semester):
    ''' Get all lectures for userset during given period.

    To do this we need to pull in a bunch of extra tables and manualy join them
    in the where cluase. The first element in the custom where is the important
    one that limits our results, the rest are simply meant for joining.
    '''

    where=[
        'common_userset_groups.group_id = common_group.id',
        'common_userset_groups.userset_id = common_userset.id',
        'common_group.id = common_lecture_groups.group_id',
        'common_lecture_groups.lecture_id = common_lecture.id'
    ]
    tables=[
        'common_userset_groups',
        'common_group',
        'common_lecture_groups'
    ]

    # TODO add exclude sub query here so that we have all the information we
    # need right away.
    select = {}

    filter = {
        'course__userset__slug': slug,
        'course__userset__semester': semester,
    }

    related = [
        'type__name',
        'room__name',
        'course__name',
    ]

    order = [
        'course__name',
        'day',
        'start_time',
        'type__name',
    ]

    return  Lecture.objects.filter(**filter).distinct().select_related(*related).extra(where=where, tables=tables, select=select).order_by(*order)


def getting_started(request):
    if request.method == 'POST' and 'slug' in request.POST:
        slug = slugify(request.POST['slug'])

        if slug.strip():
            # Default to current semester
            if datetime.now().month <= 6:
                semester = Semester(type=Semester.SPRING).get_type_display()
            else:
                semester = Semester(type=Semester.FALL).get_type_display()

            response = HttpResponseRedirect(reverse('schedule', args=[datetime.now().year, semester, slug]))

            # Store last timetable visited in a cookie so that we can populate
            # the field with a default value next time.
            response.set_cookie('last', slug, 60*60*24*7*4)
            return response
    return render_to_response('common/start.html', {
                'slug_count': UserSet.objects.values('slug').distinct().count(),
                'subscription_count': UserSet.objects.count(),
                'lecture_count': Lecture.objects.count(),
                'course_count': Course.objects.count(),
                'exam_count': Exam.objects.count(),
            }, RequestContext(request))

def schedule(request, year, semester, slug, advanced=False, week=None):
    t = request.timer
    cache_key = ':'.join(['schedule', year, semester, slug, str(advanced)])
    response = cache.get(cache_key)

    if response and 'no-cache' not in request.GET:
        t.tick('Done, returning cache')
        return response

    cursor = connection.cursor()

    # Data structure that stores what will become the html table
    table = [[[{}] for a in Lecture.DAYS] for b in Lecture.START]

    # Extra info used to get the table right
    lectures = []

    # ids of included lectures
    included = []

    # Color mapping for the courses
    color_map = {}
    color_index = 0

    # Header colspans
    span = [1] * 5

    # Array with courses to show
    courses = []
    group_forms = {}

    # Helper arrays to keep query count down
    groups = {}
    lecturers = {}
    weeks = {}
    rooms = {}

    semester = get_semester(year, semester)

    initial_lectures = get_lectures(slug, semester)

    first_day = semester.get_first_day()
    last_day = semester.get_last_day()

    exam_list = Exam.objects.filter(course__userset__slug=slug, exam_time__gt=first_day, exam_time__lt=last_day).select_related('course__name', 'course__full_name')

    t.tick('Done intializing')

    # FIXME all of these are way to naive, need a where clause
    cursor.execute('''SELECT common_lecture_rooms.lecture_id, common_room.name
                        FROM common_lecture_rooms
                        INNER JOIN common_room
                            ON (common_room.id = common_lecture_rooms.room_id)''')

    for lecture_id,name in cursor.fetchall():
        if lecture_id not in rooms:
            rooms[lecture_id] = []

        rooms[lecture_id].append(name)
    print rooms[6788]
    t.tick('Done getting rooms for lecture list')

    if advanced:
        for u in UserSet.objects.filter(slug=slug, semester=semester):
            # SQL: this causes extra queries (can be worked around, subquery?)
            initial_groups = u.groups.values_list('id', flat=True)

            # SQL: this causes extra queries (hard to work around, probably not
            # worh it)
            course_groups = Group.objects.filter(lecture__course__id=u.course_id).distinct()

            # SQL: For loop generates to quries per userset.
            group_forms[u.course_id] = GroupForm(course_groups, initial={'groups': initial_groups}, prefix=u.course_id)

        t.tick('Done creating groups forms')

        # Do three custom sql queries to prevent and explosion of sql queries
        # due to ORM. FIXME do same queries using ORM
        cursor.execute('''SELECT common_lecture_groups.lecture_id, common_group.name
                            FROM common_lecture_groups
                            INNER JOIN common_group
                                ON (common_group.id = common_lecture_groups.group_id)''')

        for lecture_id,name in cursor.fetchall():
            if lecture_id not in groups:
                groups[lecture_id] = []

            groups[lecture_id].append(name)
        t.tick('Done getting groups for lecture list')

        cursor.execute('''SELECT common_lecture_lecturers.lecture_id, common_lecturer.name
                            FROM common_lecture_lecturers
                            INNER JOIN common_lecturer
                                ON (common_lecturer.id = common_lecture_lecturers.lecturer_id)''')

        for lecture_id,name in cursor.fetchall():
            if lecture_id not in lecturers:
                lecturers[lecture_id] = []

            lecturers[lecture_id].append(name)

        t.tick('Done getting lecturers for lecture list')

        cursor.execute('''SELECT common_lecture_weeks.lecture_id, common_week.number
                            FROM common_lecture_weeks
                            INNER JOIN common_week
                                ON (common_week.id = common_lecture_weeks.week_id)''')

        for lecture_id,name in cursor.fetchall():
            if lecture_id not in weeks:
                weeks[lecture_id] = []

            weeks[lecture_id].append(name)

        t.tick('Done getting weeks for lecture list')

    for c in Course.objects.filter(userset__slug=slug, userset__semester=semester).distinct():
        # Create an array containing our courses and add the css class
        if c.id not in color_map:
            color_index = (color_index + 1) % MAX_COLORS
            color_map[c.id] = 'lecture%d' % color_index

        c.css_class = color_map[c.id]

        courses.append([c, group_forms.get(c.id)])

    t.tick('Done building course array')

    t.tick('Starting main lecture loop')
    for i,lecture in enumerate(initial_lectures.exclude(excluded_from__slug=slug)):
        # Our actual layout algorithm for handling collisions and displaying in
        # tables:

        start = lecture.start_time - Lecture.START[0][0]
        end = lecture.end_time - Lecture.END[0][0]
        rowspan = end - start + 1

        first = start

        # Keep track of which lectures are displayed
        included.append(lecture.id)

        # Try to find leftmost row that can fit our lecture, if we run out of
        # rows to test, ie IndexError, we append a fresh one to work with
        try:
            row = 0
            while start <= end:
                if table[start][lecture.day][row]:
                    # One of our time slots is taken, bump the row number and
                    # restart our search
                    row += 1
                    start = first
                else:
                    start += 1

        except IndexError:
            # We ran out of rows to check, simply append a new row
            for j,time in enumerate(Lecture.START):
                table[j][lecture.day].append({})

            # Update the header colspan
            span[lecture.day] += 1

        start = first
        remove = False

        css = [color_map[lecture.course_id]]

        if lecture.type.optional:
            css.append('optional')

        if rowspan == 1:
            css.append('single')

        while start <= end:
            # Replace the cell we found with a base containing info about our
            # lecture
            table[start][lecture.day][row] = {
                'lecture': lecture,
                'rowspan': rowspan,
                'remove': remove,
                'class': ' '.join(css),
            }

            # Add lecture to our supplementary data structure and set the
            # remove flag.
            if not remove:
                remove = True
                lectures.append({
                    'height': rowspan,
                    'i': start,
                    'j': lecture.day,
                    'm': row,
                })

            start += 1

    t.tick('Starting lecture expansion')
    for lecture in lectures:
        # Loop over supplementary data structure using this to figure out which
        # colspan expansions are safe
        i = lecture['i']
        j = lecture['j']
        m = lecture['m']
        height = lecture['height']

        expand_by = 1

        r = rooms.get(table[i][j][m]['lecture'].id, [])
        table[i][j][m]['lecture'].sql_rooms = r

        # Find safe expansion of colspan
        safe = True
        for l in xrange(m+1, len(table[i][j])):
            for k in xrange(i,i+height):
                if table[k][j][l]:
                    safe = False
                    break
            if safe:
                expand_by += 1
            else:
                break

        table[i][j][m]['colspan'] = expand_by

        # Remove cells that will get replaced by colspan
        for l in xrange(m+1,m+expand_by):
            for k in xrange(i,i+height):
                table[k][j][l]['remove'] = True
    t.tick('Done with lecture expansion')

    # TODO add second round of expansion equalising colspan

    # Insert extra cell containg times
    for i,start,end in map(lambda x,y: (x[0], x[1][1],y[1]), enumerate(Lecture.START), Lecture.END):
        table[i].insert(0, [{'time': '%s - %s' % (start, end), 'class': 'time'}])
    t.tick('Done adding times')

    # Add colors and exlude status
    if advanced:
        for i,lecture in enumerate(initial_lectures):
            initial_lectures[i].css_class =  color_map[lecture.course_id]
            initial_lectures[i].excluded  =  lecture.id not in included

            initial_lectures[i].sql_weeks = compact_sequence(weeks.get(lecture.id, []))
            initial_lectures[i].sql_groups = groups.get(lecture.id, [])
            initial_lectures[i].sql_lecturers = lecturers.get(lecture.id, [])
            initial_lectures[i].sql_rooms = rooms.get(lecture.id, [])


        t.tick('Done lecture css_clases and excluded status')

    else:
        for i,exam in enumerate(exam_list):
            exam_list[i].css_class = color_map[exam.course_id]

    t.tick('Starting render to response')
    response = render_to_response('common/schedule.html', {
                            'advanced': advanced,
                            'colspan': span,
                            'courses': courses,
                            'exams': exam_list,
                            'lectures': initial_lectures,
                            'legend': map(lambda x: x[0], courses),
                            'semester': semester,
                            'slug': slug,
                            'table': table,
                        }, RequestContext(request))

    t.tick('Saving to cache')
    cache.set(cache_key, response)

    t.tick('Returning repsonse')
    return response

def select_groups(request, year, type, slug):
    semester = get_semester(year, type)

    if request.method == 'POST':
        for c in Course.objects.filter(userset__slug=slug).distinct().order_by('id'):
            group_form = GroupForm(Group.objects.filter(lecture__course=c).distinct(), request.POST, prefix=c.id)

            if group_form.is_valid():
                set = UserSet.objects.get(course=c, slug=slug, semester=semester)
                set.groups = group_form.cleaned_data['groups']

        cache_key = ':'.join(['schedule', year, semester.get_type_display(), slug])
        cache.delete(cache_key+':False')
        cache.delete(cache_key+':True')

        logging.debug('Deleted cache key: %s' % cache_key)

    return HttpResponseRedirect(reverse('schedule-advanced', args=[semester.year,semester.get_type_display(),slug]))

def select_course(request, year, type, slug, add=False):
    semester = get_semester(year, type)

    if request.method == 'POST' and ('course_add' in request.POST or 'course_remove' in request.POST):

        cache_key = ':'.join(['schedule', year, semester.get_type_display(), slug])
        cache.delete(cache_key+':False')
        cache.delete(cache_key+':True')

        logging.debug('Deleted cache key: %s' % cache_key)

        if 'submit_add' in request.POST or add:
            lookup = []

            for l in request.POST.getlist('course_add'):
                lookup.extend(l.split())

            errors = []
            error_mail = []

            for l in lookup:
                try:
                    course = Course.objects.get(name__iexact=l.strip())
                    userset, created = UserSet.objects.get_or_create(slug=slug, course=course, semester=semester)

                    for g in Group.objects.filter(lecture__course=course).distinct():
                        userset.groups.add(g)

                except Course.DoesNotExist:
                    errors.append(l)

            if errors:
                return render_to_response('common/error.html',
                            {'courses': errors, 'slug': slug, 'year': year, 'type': semester.get_type_display()},
                            RequestContext(request))

        elif 'submit_remove' in request.POST:
            courses = [c.strip() for c in request.POST.getlist('course_remove') if c.strip()]
            sets = UserSet.objects.filter(slug__iexact=slug, course__id__in=courses)
            sets.delete()

    return HttpResponseRedirect(reverse('schedule-advanced', args=[semester.year, semester.get_type_display(), slug]))

def select_lectures(request, year,type,slug):
    if request.method == 'POST':
        excludes = request.POST.getlist('exclude')

        for userset in UserSet.objects.filter(slug=slug):
            userset.exclude = userset.course.lecture_set.filter(id__in=excludes)

        cache_key = ':'.join(['schedule', year, type, slug])
        cache.delete(cache_key+':False')
        cache.delete(cache_key+':True')

        logging.debug('Deleted cache key: %s' % cache_key)

    return HttpResponseRedirect(reverse('schedule-advanced', args=[year,type,slug]))

def ical(request, year, semester, slug, lectures=True, exams=True):
    semester = get_semester(year, semester)

    # FIXME cache the response! use request path..

    cal = vobject.iCalendar()
    cal.add('method').value = 'PUBLISH'  # IE/Outlook needs this

    if lectures:
        for l in get_lectures(slug, semester).exclude(excluded_from__slug=slug):
            weeks = l.weeks.values_list('number', flat=True)

            for d in rrule(WEEKLY,byweekno=weeks,count=len(weeks),byweekday=l.day,dtstart=datetime(int(year),1,1)):
                vevent = cal.add('vevent')
                vevent.add('summary').value = l.course.name
                vevent.add('location').value = l.room.name
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
        for e in Exam.objects.filter(course__userset__slug=slug, exam_time__gt=first_day, exam_time__lt=last_day).select_related('course__name'):
            vevent = cal.add('vevent')

            vevent.add('summary').value = 'Exam: %s (%s)' % (e.course.name, e.type)
            vevent.add('description').value = 'Exam (%s) - %s' % (e.type, e.course.full_name)
            vevent.add('dtstamp').value = datetime.now(tzlocal())

            vevent.add('uid').value = 'exam-%d@%s' % (e.id, gethostname())

            if e.handout_time:
                vevent.add('dtstart').value = e.handout_time.replace(tzinfo=tzlocal())
                vevent.add('dtend').value = e.exam_time.replace(tzinfo=tzlocal())
            else:
                vevent.add('dtstart').value = e.exam_time.replace(tzinfo=tzlocal())

                if e.duration is None:
                    pass
                elif e.duration == 30:
                    duration = timedelta(minutes=30)
                else:
                    duration = timedelta(hours=e.duration)

                if e.duration is None:
                    vevent.add('dtend').value = e.exam_time.replace(tzinfo=tzlocal())
                else:
                    vevent.add('dtend').value = e.exam_time.replace(tzinfo=tzlocal()) + duration

    icalstream = cal.serialize()

    if 'plain' in request.GET:
        response = HttpResponse(icalstream, mimetype='text/plain')
    else:
        response = HttpResponse(icalstream, mimetype='text/calendar')
        response['Filename'] = '%s.ics' % slug  # IE needs this
        response['Content-Disposition'] = 'attachment; filename=filename.ics'

    return response

# FIXME no longer in use
def list_courses(request, year, semester, slug):
    # FIXME response is not being cached and exams should be retrived more
    # effciently

    if request.method == 'POST':
        return select_course(request, year, semester, slug, add=True)

    if 'q' in request.GET:
        query = request.GET['q'].split()[-1]

        response = cache.get('course_list:%s' % query.upper())

        if not response:
            data = serializers.serialize('json', Course.objects.filter(name__istartswith=query).order_by('name'))
            response = HttpResponse(data, mimetype='text/plain')

            cache.set('course_list:%s' % query.upper(), response)

        return response

    response = cache.get('course_list')

    if not response:
        response = object_list(request, Course.objects.all(), template_object_name='course', template_name='common/course_list.html')

        cache.set('course_list', response)

    return response

def scrape_list(request):
    '''Scrape the NTNU website to retrive all available courses'''
    if not request.user.is_authenticated():
        raise Http404

    courses = scrape_courses()

    return HttpResponse(str('\n'.join([str(c) for c in courses])), mimetype='text/plain')

def scrape_exam(request, no_auth=False):
    # FIXME get into working shape
    if not request.user.is_authenticated() and not no_auth:
        raise Http404

    results = scrape_exams()

    return HttpResponse(str('\n'.join([str(r) for r in results])), mimetype='text/plain')

def scrape(request, course, no_auth=False):
    '''Retrive all lectures for a given course'''
    if not no_auth and not request.user.is_authenticated():
        raise Http404

    results = scrape_course(course)

    return HttpResponse(str('\n'.join([str(r) for r in results])), mimetype='text/plain')
