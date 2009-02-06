# encoding: utf-8

import logging
from time import time
from datetime import datetime, timedelta

from django.db.models import Q
from django.conf import settings
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponse, Http404
from django.shortcuts import render_to_response, get_object_or_404
from django.template.context import RequestContext
from django.template.defaultfilters import slugify # FIXME Replace with custom slugify
from django.views.generic.list_detail import object_list

from plan.common.models import Course, Deadline, Exam, Group, \
        Lecture, Semester, UserSet, Room, Lecturer, Week
from plan.common.forms import DeadlineForm, GroupForm, CourseNameForm, \
        ScheduleForm
from plan.common.utils import compact_sequence, ColorMap
from plan.common.timetable import Timetable
from plan.common.cache import clear_cache, get_realm, cache
#from plan.common.templatetags.slugify import slugify

# FIXME Split views that do multiple form handling tasks into seperate views
# that call the top one.

def shortcut(request, slug):
    '''Redirect users to their timetable for the current semester'''

    try:
        semester = Semester.current(from_db=True, early=True)
    except Semester.DoesNotExist:
        try:
            semester = Semester.current(from_db=True)
        except Semester.DoesNotExist:
            raise Http404

    return HttpResponseRedirect(reverse('schedule',
            args = [semester.year, semester.get_type_display(), slug]))

def getting_started(request, year=None, semester_type=None):
    '''Intial top level page that greets users'''
    schedule_form = None

    if year and semester_type:
        semester = Semester(year=year, type=semester_type)
        qs = Semester.objects.filter(year=semester.year, type=semester.type)
    else:
        semester = Semester.current(early=True)
        qs = None

    # Redirect user to their timetable
    if request.method == 'POST' and 'slug' in request.POST:
        schedule_form = ScheduleForm(request.POST, queryset=qs)

        if schedule_form.is_valid():
            slug = schedule_form.cleaned_data['slug']
            semester = schedule_form.cleaned_data['semester'] or \
                semester

            if slug.strip():
                response = HttpResponseRedirect(reverse('schedule', args=[
                    semester.year, semester.get_type_display(), slug]))

                # Store last timetable visited in a cookie so that we can populate
                # the field with a default value next time.
                response.set_cookie('last', slug, 60*60*24*7*4)
                return response

    realm = get_realm(semester)
    context = cache.get('stats', realm=realm)

    if not context or not request.use_cache:
        try:
            semester = Semester.objects.get(year=semester.year, type=semester.type)
        except Semester.DoesNotExist:
            if not year and not semester_type:
                return render_to_response('start.html', {'missing': True}, RequestContext(request))
            return HttpResponseRedirect(reverse('frontpage'))

        if not schedule_form:
            schedule_form = ScheduleForm(initial={'semester': semester.id,
                'slug': '%s'}, queryset=qs)

        # FIXME, move all of this into get stats
        slug_count = int(UserSet.objects.filter(semester__in=[semester]). \
                values('slug').distinct().count())

        subscription_count = int(UserSet.objects.filter(semester__in=\
                [semester]).count())

        deadline_count = int(Deadline.objects.filter(userset__semester__in=\
                [semester]).count())

        stats, limit = Course.get_stats(semester=semester)

        context = {
            'color_map': ColorMap(),
            'current': semester,
            'slug_count': slug_count,
            'subscription_count': subscription_count,
            'deadline_count': deadline_count,
            'stats': stats,
            'limit': limit,
            'schedule_form': '\n'.join([str(f) for f in schedule_form]),
        }

        cache.set('stats', context, settings.CACHE_TIME_STATS, realm=realm)

    if '%s' in context['schedule_form']:
        context['schedule_form'] = context['schedule_form'] % request.COOKIES.get('last', '')

    return render_to_response('start.html', context, RequestContext(request))

def course_query(request, year, semester_type):
    limit = request.GET.get('limit', '10')
    query = request.GET.get('q', '').strip()
    cache_key = ':'.join([request.path, query, limit])

    if limit > 100:
        limit = 100

    response = cache.get(cache_key, prefix=True)

    if response and request.use_cache:
        return response

    response = HttpResponse(mimetype='text/plain; charset=utf-8')
    semester = Semester(year=year, type=semester_type)

    if not query:
        return response

    name_or_full_name = Q(name__icontains=query) | Q(full_name__icontains=query)

    courses = Course.objects.filter(name_or_full_name,
        name__regex='[0-9]+', # FIXME assumes course codes must contain numbers
        semesters__year__exact=semester.year,
        semesters__type__exact=semester.type)[:limit]

    for course in courses:
        response.write('%s|%s\n' % (course.name, course.full_name))

    cache.set(cache_key, response, settings.CACHE_TIME_QUERY, prefix=True)

    return response

def schedule(request, year, semester_type, slug, advanced=False,
        week=None, all=False, deadline_form=None, cache_page=True):
    '''Page that handels showing schedules'''

    # Don't do any db stuff until after the cache lines further down
    semester = Semester(year=year, type=semester_type)
    current = Semester.current()

    if semester.year != current.year and semester.type != current.type:
        url = request.path
    elif not all and not week and not advanced:
        # Start new week on saturdays
        week = (datetime.now() + timedelta(days=2)).isocalendar()[1]
        url = reverse('schedule-week', args=[semester.year, semester.type, slug, week])
    else:
        url = request.path

    realm = get_realm(semester, slug)
    response = cache.get(url, realm=realm)

    if response and request.use_cache:
        return response

    # Color mapping for the courses
    color_map = ColorMap()

    group_forms = {}

    semester = get_object_or_404(Semester, year=semester.year, type=semester.type)

    # Start setting up queries
    courses = Course.objects.get_courses(year, semester.type, slug)
    deadlines = Deadline.objects.get_deadlines(year, semester.type, slug)
    lectures = Lecture.objects.get_lectures(year, semester.type, slug, week)
    exams = Exam.objects.get_exams(year, semester.type, slug)

    # Use get_related to cut query counts
    lecturers = Lecture.get_related(Lecturer, lectures)
    groups = Lecture.get_related(Group, lectures)
    rooms = Lecture.get_related(Room, lectures)
    weeks = Lecture.get_related(Week, lectures, field='number')

    min_week, max_week = 0, 0
    for w in weeks.values():
        if not min_week or min_week > w[0]:
            min_week = w[0]

        if not max_week or max_week < w[-1]:
            max_week = w[-1]

    # Init colors in predictable maner
    for c in courses:
        color_map[c.id]

    # Create Timetable
    table = Timetable(lectures, rooms)
    if lectures:
        table.place_lectures()
        table.do_expansion()
    table.add_last_marker()
    table.insert_times()

    # Add extra info to lectures
    for lecture in lectures:
        compact_weeks = compact_sequence(weeks.get(lecture.id, []))

        lecture.sql_weeks = compact_weeks
        lecture.sql_groups = groups.get(lecture.id, [])
        lecture.sql_lecturers = lecturers.get(lecture.id, [])
        lecture.sql_rooms = rooms.get(lecture.id, [])

    if advanced:
        usersets = UserSet.objects.get_usersets(year, semester.type, slug)

        # Set up deadline form
        if not deadline_form:
            deadline_form = DeadlineForm(usersets)

        if courses:
            course_groups = Course.get_groups(year, semester.type, [u.course_id for u in usersets])
            selected_groups = UserSet.get_groups(year, semester.type, slug)

            for u in usersets:
                if not course_groups.get(u.course_id, False):
                    continue

                group_forms[u.course_id] = GroupForm(course_groups[u.course_id],
                        initial={'groups': selected_groups.get(u.id, [])},
                        prefix=u.course_id)

        # Set up group forms and course name forms
        for course in courses:
            course.group_form = group_forms.get(course.id, None)

            name = course.alias or ''
            course.name_form = CourseNameForm(initial={'name': name},
                     prefix=course.id)

    next_semester = Semester.current().next()

    if next_semester.year == semester.year and \
            next_semester.type == semester.type:
        next_message = False
    elif not Semester.objects.filter(year=next_semester.year, type=next_semester.type).count():
        next_message = False
    else:
        next_message = UserSet.objects.get_usersets(next_semester.year, next_semester.type, slug).count()
        next_message = next_message == 0

    group_help = cache.get('group-help', 0, realm=realm)

    week_range = range(min_week, max_week+1)

    if not min_week or not max_week:
        week_range = []

    response = render_to_response('schedule.html', {
            'advanced': advanced,
            'color_map': color_map,
            'courses': courses,
            'deadline_form': deadline_form,
            'deadlines': deadlines,
            'exams': exams,
            'group_help': group_help,
            'next_message': next_message,
            'lectures': lectures,
            'semester': semester,
            'next_semester': next_semester,
            'slug': slug,
            'timetable': table,
            'week': week,
            'weeks': week_range,
        }, RequestContext(request))

    if cache_page:
        if deadlines:
            # time until next deadline
            cache_time = deadlines[0].get_seconds()
        else:
            # default cache time
            cache_time = settings.CACHE_TIME_SCHECULDE

        group_help -= time()

        if group_help > 0 and group_help < cache_time:
            cache_time = group_help

        cache.set(url, response, cache_time, realm=realm)
    return response

def select_groups(request, year, semester_type, slug):
    '''Form handler for selecting groups to use in schedule'''

    semester = Semester(year=year, type=semester_type)

    if request.method == 'POST':
        courses = Course.objects.get_courses(year, semester.type, slug)

        course_groups = Course.get_groups(year, semester.type, [c.id for c in courses])

        for c in courses:
            try:
                groups = course_groups[c.id]
            except KeyError: # Skip courses without groups
                continue

            group_form = GroupForm(groups, request.POST, prefix=c.id)

            if group_form.is_valid():
                userset = UserSet.objects.get_usersets(year,
                        semester.type, slug).get(course=c)

                userset.groups = group_form.cleaned_data['groups']

        clear_cache(semester, slug)

    return HttpResponseRedirect(reverse('schedule-advanced',
            args=[semester.year,semester.get_type_display(),slug]))

def new_deadline(request, year, semester_type, slug):
    '''Handels addition of tasks, reshows schedule view if form does not
       validate'''
    semester = Semester(year=year, type=semester_type)

    if request.method == 'POST':
        clear_cache(semester, slug)

        if 'submit_add' in request.POST:
            usersets = UserSet.objects.get_usersets(year, semester.type, slug)
            deadline_form = DeadlineForm(usersets, request.POST)

            if deadline_form.is_valid():
                deadline_form.save()
            else:
                return schedule(request, year, semester_type, slug, advanced=True,
                        deadline_form=deadline_form, cache_page=False)

        elif 'submit_remove' in request.POST:
            logging.debug(request.POST.getlist('deadline_remove'))
            Deadline.objects.get_deadlines(year, semester.type, slug).filter(
                    id__in=request.POST.getlist('deadline_remove')
                ).delete()

    return HttpResponseRedirect(reverse('schedule-advanced',
            args = [semester.year,semester.get_type_display(),slug]))

def copy_deadlines(request, year, semester_type, slug):
    '''Handles importing of deadlines'''

    semester = Semester(year=year, type=semester_type)

    if request.method == 'POST':
        if 'slugs' in request.POST:
            slugs = request.POST['slugs'].replace(',', ' ').split()

            color_map = ColorMap()

            courses = Course.objects.get_courses(year, semester.type, slug). \
                    distinct()

            # Init color map
            for c in courses:
                color_map[c.id]

            deadlines = Deadline.objects.filter(
                    userset__slug__in=slugs,
                    userset__semester__year__exact=year,
                    userset__semester__type__exact=semester.type,
                    userset__course__in=courses,
                ).select_related(
                    'userset__course__id'
                ).exclude(userset__slug=slug)

            return render_to_response('select_deadlines.html', {
                    'color_map': color_map,
                    'deadlines': deadlines,
                    'semester': semester,
                    'slug': slug,
                }, RequestContext(request))

        elif 'deadline_id' in request.POST:
            deadline_ids = request.POST.getlist('deadline_id')
            deadlines = Deadline.objects.filter(
                    id__in=deadline_ids,
                    userset__semester__year__exact=year,
                    userset__semester__type__exact=semester.type,
                )

            for d in deadlines:
                userset = UserSet.objects.get_usersets(year, semester.type,
                    slug).get(course=d.userset.course)

                Deadline.objects.get_or_create(
                        userset=userset,
                        date=d.date,
                        time=d.time,
                        task=d.task
                )
            clear_cache(semester, slug)

    return HttpResponseRedirect(reverse('schedule',
            args=[semester.year,semester.get_type_display(),slug]))

def select_course(request, year, semester_type, slug, add=False):
    '''Handle selecting of courses from course list, change of names and
       removeall of courses'''

    # FIXME split ut three sub functions into seperate functions?

    semester = Semester(year=year, type=semester_type)
    realm = get_realm(semester, slug)

    try:
        semester = Semester.objects.get(year=year, type=semester.type)
    except Semester.DoesNotExist:
        return HttpResponseRedirect(reverse('schedule', args=
                [year,semester.get_type_display(),slug]))

    if request.method == 'POST':
        clear_cache(semester, slug)

        if 'submit_add' in request.POST or add:
            lookup = []

            for l in request.POST.getlist('course_add'):
                lookup.extend(l.replace(',', '').split())

            usersets = set(UserSet.objects.get_usersets(semester.year,
                semester.type, slug).values_list('course__name', flat=True))

            errors = []
            max_group_count = 0
            to_many_usersets = False

            for l in lookup:
                try:
                    if len(usersets) > settings.TIMETABLE_MAX_COURSES:
                        to_many_usersets = True
                        break

                    course = Course.objects.get(
                            name__iexact=l.strip(),
                            semesters__in=[semester],
                        )
                    userset, created = UserSet.objects.get_or_create(
                            slug=slug,
                            course=course,
                            semester=semester
                        )

                    usersets.add(course.name)

                    groups = Group.objects.filter(
                            lecture__course=course
                        ).distinct()

                    userset.groups = groups

                    if len(groups) > max_group_count:
                        max_group_count = len(groups)

                except Course.DoesNotExist:
                    errors.append(l)

            if max_group_count > 2:
                cache.set('group-help', int(time())+settings.CACHE_TIME_HELP,
                        settings.CACHE_TIME_HELP, realm=realm)

            if errors or to_many_usersets:
                return render_to_response('error.html', {
                        'courses': errors,
                        'max': settings.TIMETABLE_MAX_COURSES,
                        'slug': slug,
                        'year': year,
                        'type': semester.get_type_display(),
                        'to_many_usersets': to_many_usersets,
                    }, RequestContext(request))

        elif 'submit_remove' in request.POST:
            courses = []
            for c in request.POST.getlist('course_remove'):
                if c.strip():
                    courses.append(c.strip())

            UserSet.objects.get_usersets(year, semester.type, slug). \
                    filter(course__id__in=courses).delete()

        elif 'submit_name' in request.POST:
            usersets = UserSet.objects.get_usersets(year, semester.type, slug)

            for u in usersets:
                form = CourseNameForm(request.POST, prefix=u.course_id)

                if form.is_valid():
                    name = form.cleaned_data['name'].strip()

                    if name.upper() == u.course.name.upper() or name == "":
                        # Leave as blank if we match the current course name
                        name = ""

                    u.name = name
                    u.save()

    return HttpResponseRedirect(reverse('schedule-advanced',
            args=[semester.year, semester.get_type_display(), slug]))

def select_lectures(request, year, semester_type, slug):
    '''Handle selection of lectures to hide'''
    semester = Semester(year=year, type=semester_type)

    if request.method == 'POST':
        excludes = request.POST.getlist('exclude')

        usersets = UserSet.objects.get_usersets(year, semester.type, slug)

        for userset in usersets:
            if excludes:
                userset.exclude = userset.course.lecture_set.filter(id__in=excludes)
            else:
                userset.exclude.clear()

        clear_cache(semester, slug)

    return HttpResponseRedirect(reverse('schedule-advanced',
            args=[semester.year, semester.get_type_display(), slug]))

def list_courses(request, year, semester_type, slug):
    '''Display a list of courses based on when exam is'''

    if request.method == 'POST':
        return select_course(request, year, semester_type, slug, add=True)

    semester = Semester(year=year, type=semester_type)

    key = '/'.join([str(semester.year), semester.get_type_display(), 'courses'])
    response = cache.get(key, prefix=True)

    if not response or not request.use_cache:

        courses = Course.objects.get_courses_with_exams(year, semester.type)

        response = render_to_response('course_list.html', {
                'semester': semester,
                'course_list': courses,
            }, RequestContext(request))

        cache.set(key, response, prefix=True)

    return response
