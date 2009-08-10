# Copyright 2008, 2009 Thomas Kongevold Adamcik

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

import logging
from time import time
from datetime import datetime, timedelta

from django.db.models import Q
from django.conf import settings
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponse, Http404
from django.shortcuts import render_to_response, get_object_or_404
from django.template.context import RequestContext
from django.views.generic.list_detail import object_list
from django.utils.html import escape
from django.utils.text import truncate_words

from plan.common.models import Course, Deadline, Exam, Group, \
        Lecture, Semester, UserSet, Room, Lecturer, Week, Student
from plan.common.forms import DeadlineForm, GroupForm, CourseNameForm, \
        ScheduleForm
from plan.common.utils import compact_sequence, ColorMap
from plan.common.timetable import Timetable
from plan.common.cache import clear_cache, get_realm, cache
from plan.common.templatetags.slugify import slugify

# FIXME split into frontpage/semester, course, deadline, schedule files
# FIXME Split views that do multiple form handling tasks into seperate views
# that call the top one.

# To allow for overriding of the codes idea of now() for tests
now = datetime.now

def shortcut(request, slug):
    '''Redirect users to their timetable for the current semester'''

    # FIXME this logic should be hidden by current()
    try:
        semester = Semester.current(from_db=True, early=True)
    except Semester.DoesNotExist:
        try:
            semester = Semester.current(from_db=True)
        except Semester.DoesNotExist:
            raise Http404

    return HttpResponseRedirect(reverse('schedule',
            args = [semester.year, semester.type, slug]))

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
            semester = schedule_form.cleaned_data['semester'] or semester

            response = HttpResponseRedirect(reverse('schedule', args=[
                semester.year, semester.type, slug]))

            # Store last timetable visited in a cookie so that we can populate
            # the field with a default value next time.
            response.set_cookie('last', slug, settings.TIMETABLE_COOKIE_AGE)
            return response

    realm = get_realm(semester)
    response = cache.get('frontpage', realm=realm)

    if response and getattr(request, 'use_cache', True):
        return response

    try:
        semester = Semester.objects.get(year=semester.year, type=semester.type)
    except Semester.DoesNotExist:
        if not year and not semester_type:
            return render_to_response('start.html', {'missing': True}, RequestContext(request))
        return HttpResponseRedirect(reverse('frontpage'))

    if not schedule_form:
        schedule_form = ScheduleForm(initial={'semester': semester.id}, queryset=qs)

    context = Course.get_stats(semester=semester)
    context.update({
        'color_map': ColorMap(hex=True),
        'current': semester,
        'schedule_form': schedule_form,
    })

    response = render_to_response('start.html', context, RequestContext(request))

    cache.set('frontpage', response, settings.CACHE_TIME_FRONTPAGE, realm=realm)

    return response

def course_query(request, year, semester_type):
    limit = request.GET.get('limit', '10')
    query = request.GET.get('q', '').strip()

    cache_key = ':'.join([request.path, slugify(query), limit])
    cache_key = cache_key.lower()

    if limit > settings.TIMETABLE_AJAX_LIMIT:
        limit = settings.TIMETABLE_AJAX_LIMIT

    response = cache.get(cache_key, prefix=True)

    if response and getattr(request, 'use_cache', True):
        return response

    response = HttpResponse(mimetype='text/plain; charset=utf-8')
    semester = Semester(year=year, type=semester_type)

    if not query:
        return response

    courses = Course.objects.search(semester.year, semester.type,
        query, limit)

    for course in courses:
        code = escape(course.code)
        name = escape(truncate_words(course.name, 5))
        response.write(u'%s|%s\n' % (code, name or u'?'))

    cache.set(cache_key, response, settings.CACHE_TIME_AJAX, prefix=True)

    return response

def schedule(request, year, semester_type, slug, advanced=False,
        week=None, all=False, deadline_form=None, cache_page=True):
    '''Page that handels showing schedules'''

    # Don't do any db stuff until after the cache lines further down
    semester = Semester(year=year, type=semester_type)
    current = Semester.current()

    # Start new week on saturdays
    current_week = (now() + timedelta(days=2)).isocalendar()[1]

    # FIXME refactor to get_current_week...
    if semester.year != current.year and semester.type != current.type:
        url = request.path
    elif not all and not week and not advanced:
        url = reverse('schedule-week', args=[semester.year, semester.type, slug, current_week])
    else:
        url = request.path

    if week:
        week = int(week)

    if week is not None and (week <= 0 or week > 53):
        raise Http404

    realm = get_realm(semester, slug)
    response = cache.get(url, realm=realm)

    if response and getattr(request, 'use_cache', True):
        return response

    # Color mapping for the courses
    color_map = ColorMap(hex=True)

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
    weeks = Lecture.get_related(Week, lectures, field='number', use_extra=False)

    schedule_weeks = set()
    for lecture_week_set in weeks.values():
        for lecture_week in lecture_week_set:
            schedule_weeks.add(lecture_week)

    schedule_weeks = list(schedule_weeks)
    schedule_weeks.sort()

    if schedule_weeks:
        schedule_weeks = range(schedule_weeks[0], schedule_weeks[-1]+1)

    if current_week not in schedule_weeks and not week and not all and not advanced:
        return HttpResponseRedirect(reverse('schedule-all',
                args=[semester.year,semester.type,slug]))

    try:
        next_week = schedule_weeks[schedule_weeks.index(week)+1]
    except (IndexError, ValueError):
        next_week = None
    try:
        if schedule_weeks.index(week) != 0:
            prev_week = schedule_weeks[schedule_weeks.index(week)-1]
        else:
            prev_week = None
    except (IndexError, ValueError):
        prev_week = None

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
                userset_groups = list(course_groups.get(u.course_id, []))
                initial_groups = list(selected_groups.get(u.id, []))

                if not userset_groups:
                    continue

                group_forms[u.course_id] = GroupForm(course_groups[u.course_id],
                        initial={'groups': initial_groups},
                        prefix=u.course_id)

        # Set up group forms and course name forms
        for course in courses:
            course.group_form = group_forms.get(course.id, None)

            code = course.alias or ''
            course.name_form = CourseNameForm(initial={'name': code},
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

    response = render_to_response('schedule.html', {
            'advanced': advanced,
            'all': all,
            'color_map': color_map,
            'courses': courses,
            'current': (week == current_week),
            'current_week': current_week,
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
            'next_week': next_week,
            'prev_week': prev_week,
            'weeks': schedule_weeks,
        }, RequestContext(request))

    if cache_page:
        current_time = now()
        future_deadlines = filter(lambda d: current_time < d.datetime, deadlines)

        if future_deadlines:
            # time until next deadline
            cache_time = future_deadlines[0].seconds
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
            args=[semester.year,semester.type,slug]))

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
            args = [semester.year,semester.type,slug]))

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
                    userset__student__slug__in=slugs,
                    userset__course__in=courses,
                ).select_related(
                    'userset__course__id'
                ).exclude(userset__student__slug=slug)

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
                    userset__course__semester__year__exact=year,
                    userset__course__semester__type__exact=semester.type,
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

    return HttpResponseRedirect(reverse('schedule-advanced',
            args=[semester.year,semester.type,slug]))

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
                [year,semester.type,slug]))

    if request.method == 'POST':
        clear_cache(semester, slug)

        if 'submit_add' in request.POST or add:
            lookup = []

            for l in request.POST.getlist('course_add'):
                lookup.extend(l.replace(',', '').split())

            usersets = set(UserSet.objects.get_usersets(semester.year,
                semester.type, slug).values_list('course__code', flat=True))

            errors = []
            max_group_count = 0
            to_many_usersets = False

            student, created = Student.objects.get_or_create(slug=slug)

            for l in lookup:
                try:
                    if len(usersets) > settings.TIMETABLE_MAX_COURSES:
                        to_many_usersets = True
                        break

                    course = Course.objects.get(
                            code__iexact=l.strip(),
                            semester=semester,
                        )
                    userset, created = UserSet.objects.get_or_create(
                            student=student,
                            course=course,
                        )

                    usersets.add(course.code)

                    groups = Group.objects.filter(
                            lecture__course=course
                        ).distinct()

                    userset.groups = groups

                    if len(groups) > max_group_count:
                        max_group_count = len(groups)

                except Course.DoesNotExist:
                    errors.append(l)

            if UserSet.objects.filter(student=student, course__semester__year__exact=semester.year,
                course__semester__type=semester.type).count() == 0:
            
                print 'delete'
                student.delete()

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

                    if name.upper() == u.course.code.upper() or name == "":
                        # Leave as blank if we match the current course name
                        name = ""

                    u.name = name
                    u.save()

    return HttpResponseRedirect(reverse('schedule-advanced',
            args=[semester.year, semester.type, slug]))

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
            args=[semester.year, semester.type, slug]))

def list_courses(request, year, semester_type, slug):
    '''Display a list of courses based on when exam is'''

    if request.method == 'POST':
        return select_course(request, year, semester_type, slug, add=True)

    semester = Semester(year=year, type=semester_type)

    key = '/'.join([str(semester.year), semester.type, 'courses'])
    response = cache.get(key, prefix=True)

    if not response or not getattr(request, 'use_cache', True):

        courses = Course.objects.get_courses_with_exams(year, semester.type)

        response = render_to_response('course_list.html', {
                'semester': semester,
                'course_list': courses,
            }, RequestContext(request))

        cache.set(key, response, prefix=True)

    return response
