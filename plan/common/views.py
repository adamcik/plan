# Copyright 2008, 2009, 2010 Thomas Kongevold Adamcik,
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

import logging
import datetime

from django import http
from django import shortcuts
from django.conf import settings
from django.db import connection
from django.utils import html
from django.utils import text

from plan.common.models import Course, Deadline, Exam, Group, \
        Lecture, Semester, Subscription, Room, Lecturer, Week, Student
from plan.common.forms import DeadlineForm, GroupForm, CourseAliasForm, \
        ScheduleForm
from plan.common.utils import ColorMap, max_number_of_weeks
from plan.common.timetable import Timetable
from plan.cache import clear_cache, compress, decompress
from plan.common.templatetags.slugify import slugify

# FIXME split into frontpage/semester, course, deadline, schedule files
# FIXME Split views that do multiple form handling tasks into seperate views
# that call the top one.

# To allow for overriding of the codes idea of now() for tests
now = datetime.datetime.now

# Start new week on saturdays
get_current_week = lambda: (now() + datetime.timedelta(days=2)).isocalendar()[1]

def shortcut(request, slug):
    '''Redirect users to their timetable for the current semester'''

    # FIXME this logic should be hidden by current()
    try:
        semester = Semester.current(from_db=True, early=True)
    except Semester.DoesNotExist:
        try:
            semester = Semester.current(from_db=True)
        except Semester.DoesNotExist:
            raise http.Http404

    return schedule_current(request, semester.year, semester.type, slug)

def getting_started(request, year=None, semester_type=None):
    '''Intial top level page that greets users'''
    schedule_form = None

    if year and semester_type:
        semester = Semester(year=year, type=semester_type)
        qs = Semester.objects.filter(year=semester.year, type=semester.type)
        cache_key = 'frontpage-semester'
    else:
        semester = Semester.current(early=True)
        qs = None
        cache_key = 'frontpage'

    # Redirect user to their timetable
    if request.method == 'POST' and 'slug' in request.POST:
        schedule_form = ScheduleForm(request.POST, queryset=qs)

        if schedule_form.is_valid():
            slug = schedule_form.cleaned_data['slug']
            semester = schedule_form.cleaned_data['semester'] or semester

            response = schedule_current(request, semester.year, semester.type, slug)

            # Store last timetable visited in a cookie so that we can populate
            # the field with a default value next time.
            response.set_cookie('last', slug, settings.TIMETABLE_COOKIE_AGE)
            return response

    response = request.cache.get(cache_key)

    if response:
        return response

    try:
        semester = Semester.objects.get(year=semester.year, type=semester.type)
    except Semester.DoesNotExist:
        if not year and not semester_type:
            return shortcuts.render(request, 'start.html', {'missing': True})
        return shortcuts.redirect('frontpage')

    if not schedule_form:
        schedule_form = ScheduleForm(queryset=qs)

    context = Course.get_stats(semester=semester)
    context.update({
        'color_map': ColorMap(hex=True),
        'current': semester,
        'schedule_form': schedule_form,
    })

    response = shortcuts.render(request, 'start.html', context)

    request.cache.set(cache_key, response, settings.CACHE_TIME_FRONTPAGE)

    return response

def course_query(request, year, semester_type):
    limit = request.GET.get('limit', '10')
    query = request.GET.get('q', '').strip()[:100]

    if limit > settings.TIMETABLE_AJAX_LIMIT:
        limit = settings.TIMETABLE_AJAX_LIMIT

    cache_key = ':'.join([request.path, slugify(query), '%d' % limit])
    cache_key = cache_key.lower()

    response = request.cache.get(cache_key, realm=False)

    if response:
        return response

    response = http.HttpResponse(mimetype='text/plain; charset=utf-8')

    if not query:
        return response

    semester = Semester(year=year, type=semester_type)
    courses = Course.objects.search(semester.year, semester.type,
        query, limit)

    for course in courses:
        code = html.escape(course.code)
        name = html.escape(text.truncate_words(course.name, 5))
        response.write(u'%s|%s\n' % (code, name or u'?'))

    request.cache.set(cache_key, response, settings.CACHE_TIME_AJAX,
        realm=False)

    return response

def schedule_current(request, year, semester_type, slug):
    if Semester(year=year, type=semester_type).is_current:
        current_week = get_current_week()

        return shortcuts.redirect(
            'schedule-week', year, semester_type, slug, current_week)

    return shortcuts.redirect('schedule', year, semester_type, slug)

def schedule(request, year, semester_type, slug, advanced=False,
        week=None, all=False, deadline_form=None, cache_page=True):
    '''Page that handels showing schedules'''

    # Don't do any db stuff until after the cache lines further down
    semester = Semester(year=year, type=semester_type)
    response = None

    current_week = get_current_week()

    if week:
        week = int(week)
        max_week = max_number_of_weeks(semester.year)

    if week is not None:
        if (week <= 0 or week > max_week):
            raise http.Http404

    if cache_page:
        response = request.cache.get(request.path)

    if response:
        return response

    # Color mapping for the courses
    color_map = ColorMap(hex=True)

    semester = shortcuts.get_object_or_404(Semester,
                                           year=semester.year,
                                           type=semester.type)

    try:
        student = Student.objects.distinct().get(slug=slug, subscription__course__semester=semester)
    except Student.DoesNotExist:
        student = None

    # Start setting up queries
    courses = Course.objects.get_courses(year, semester.type, slug)
    deadlines = Deadline.objects.get_deadlines(year, semester.type, slug)
    lectures = Lecture.objects.get_lectures(year, semester.type, slug, week)
    exams = Exam.objects.get_exams(year, semester.type, slug)

    # Use get_related to cut query counts
    lecturers = Lecture.get_related(Lecturer, lectures)
    groups = Lecture.get_related(Group, lectures)
    rooms = Lecture.get_related(Room, lectures, fields=['name', 'url'])
    weeks = Lecture.get_related(Week, lectures, fields=['number'], use_extra=False)

    schedule_weeks = set()
    for lecture_week_set in weeks.values():
        for lecture_week in lecture_week_set:
            schedule_weeks.add(lecture_week)

    schedule_weeks = list(schedule_weeks)
    schedule_weeks.sort()

    if schedule_weeks:
        schedule_weeks = range(schedule_weeks[0], schedule_weeks[-1]+1)

    next_week = None
    prev_week = None

    if week and week < max_week:
        next_week = week+1

    if week and week > 1:
        prev_week = week-1

    # Init colors in predictable maner
    for c in courses:
        color_map[c.id]

    # Create Timetable
    table = Timetable(lectures)

    if week:
        table.set_week(semester.year, week)

    if lectures:
        table.place_lectures()
        table.do_expansion()

    table.add_last_marker()
    table.insert_times()

    if advanced:
        subscriptions = Subscription.objects.get_subscriptions(year, semester.type, slug)

        # Set up deadline form
        if not deadline_form:
            deadline_form = DeadlineForm(subscriptions)

        # Set up and course name forms
        for course in courses:
            alias = course.alias or ''
            course.alias_form = CourseAliasForm(initial={'alias': alias},
                     prefix=course.id)

    next_semester = Semester.current().next()

    if next_semester.year == semester.year and \
            next_semester.type == semester.type:
        next_message = False
    elif not Semester.objects.filter(year=next_semester.year, type=next_semester.type).count():
        next_message = False
    else:
        next_message = Subscription.objects.get_subscriptions(next_semester.year, next_semester.type, slug).count()
        next_message = next_message == 0

    response = shortcuts.render(request, 'schedule.html', {
            'advanced': advanced,
            'all': all,
            'color_map': color_map,
            'courses': courses,
            'current': (week == current_week),
            'current_week': current_week,
            'deadline_form': deadline_form,
            'deadlines': deadlines,
            'exams': exams,
            'next_message': next_message,
            'lectures': lectures,
            'semester': semester,
            'next_semester': next_semester,
            'slug': slug,
            'timetable': table,
            'week': week,
            'next_week': next_week,
            'prev_week': prev_week,
            'rooms': rooms,
            'weeks': schedule_weeks,
            'groups': groups,
            'lecturers': lecturers,
            'lecture_weeks': weeks,
            'student': student,
        })

    if cache_page:
        current_time = now()
        future_deadlines = filter(lambda d: current_time < d.datetime, deadlines)

        if future_deadlines:
            # time until next deadline
            cache_time = future_deadlines[0].seconds
        else:
            # default cache time
            cache_time = settings.CACHE_TIME_SCHECULDE

        request.cache.set(request.path, response, cache_time)

    return response

def select_groups(request, year, semester_type, slug):
    '''Form handler for selecting groups to use in schedule'''

    semester = Semester(year=year, type=semester_type)
    courses = Course.objects.get_courses(year, semester.type, slug)
    course_groups = Course.get_groups(year, semester.type, [c.id for c in courses])

    if request.method == 'POST':
        for c in courses:
            try:
                groups = course_groups[c.id]
            except KeyError: # Skip courses without groups
                continue

            group_form = GroupForm(groups, request.POST, prefix=c.id)

            if group_form.is_valid():
                subscription = Subscription.objects.get_subscriptions(year,
                        semester.type, slug).get(course=c)

                subscription.groups = group_form.cleaned_data['groups']

        clear_cache(semester, slug)

        return shortcuts.redirect(
            'schedule-advanced', semester.year, semester.type,slug)

    color_map = ColorMap(hex=True)
    subscription_groups = Subscription.get_groups(year, semester.type, slug)
    all_subscripted_groups = set()

    for groups in subscription_groups.values():
        for group in groups:
            all_subscripted_groups.add(group)

    for c in courses:
        color_map[c.id]
        subscription_id = c.subscription_set.get(student__slug=slug).pk

        try:
            groups = course_groups[c.id]
        except KeyError: # Skip courses without groups
            continue

        initial_groups = subscription_groups.get(subscription_id, all_subscripted_groups)

        c.group_form = GroupForm(groups, prefix=c.id, initial={'groups': initial_groups})

    return shortcuts.render(request, 'select_groups.html', {
            'semester': semester,
            'slug': slug,
            'courses': courses,
            'color_map': color_map,
        })

def toggle_deadlines(request, year, semester_type, slug):
    semester = Semester(year=year, type=semester_type)
    student = Student.objects.distinct().get(slug=slug,
        subscription__course__semester__year__exact=year,
        subscription__course__semester__type=semester_type)

    if request.method == 'POST':
        student.show_deadlines = not student.show_deadlines
        student.save()
        clear_cache(semester, slug)

    return shortcuts.redirect(
        'schedule-advanced', semester.year, semester.type, slug)

def new_deadline(request, year, semester_type, slug):
    '''Handels addition of tasks, reshows schedule view if form does not
       validate'''
    semester = Semester(year=year, type=semester_type)

    if request.method == 'POST':
        clear_cache(semester, slug)

        if 'submit_add' in request.POST:
            subscriptions = Subscription.objects.get_subscriptions(year, semester.type, slug)
            deadline_form = DeadlineForm(subscriptions, request.POST)

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

    return shortcuts.redirect(
        'schedule-advanced', semester.year, semester.type, slug)

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
                    subscription__student__slug__in=slugs,
                    subscription__course__in=courses,
                ).select_related(
                    'subscription__course__id'
                ).exclude(subscription__student__slug=slug)

            return shortcuts.render(request, 'select_deadlines.html', {
                    'color_map': color_map,
                    'deadlines': deadlines,
                    'semester': semester,
                    'slug': slug,
                })

        elif 'deadline_id' in request.POST:
            deadline_ids = request.POST.getlist('deadline_id')
            deadlines = Deadline.objects.filter(
                    id__in=deadline_ids,
                    subscription__course__semester__year__exact=year,
                    subscription__course__semester__type__exact=semester.type,
                )

            for d in deadlines:
                subscription = Subscription.objects.get_subscriptions(year, semester.type,
                    slug).get(course=d.subscription.course)

                Deadline.objects.get_or_create(
                        subscription=subscription,
                        date=d.date,
                        time=d.time,
                        task=d.task
                )
            clear_cache(semester, slug)

    return shortcuts.redirect(
        'schedule-advanced', semester.year, semester.type, slug)

def select_course(request, year, semester_type, slug, add=False):
    '''Handle selecting of courses from course list, change of names and
       removeall of courses'''

    # FIXME split ut three sub functions into seperate functions?

    semester = Semester(year=year, type=semester_type)

    try:
        semester = Semester.objects.get(year=year, type=semester.type)
    except Semester.DoesNotExist:
        return shortcuts.redirect('schedule', year, semester.type, slug)

    if request.method == 'POST':
        clear_cache(semester, slug)

        if 'submit_add' in request.POST or add:
            lookup = []

            for l in request.POST.getlist('course_add'):
                lookup.extend(l.replace(',', '').split())

            subscriptions = set(Subscription.objects.get_subscriptions(semester.year,
                semester.type, slug).values_list('course__code', flat=True))

            errors = []
            to_many_subscriptions = False

            student, created = Student.objects.get_or_create(slug=slug)

            for l in lookup:
                try:
                    if len(subscriptions) > settings.TIMETABLE_MAX_COURSES:
                        to_many_subscriptions = True
                        break

                    course = Course.objects.get(
                            code__iexact=l.strip(),
                            semester=semester,
                        )

                    Subscription.objects.get_or_create(
                            student=student,
                            course=course,
                        )
                    subscriptions.add(course.code)

                except Course.DoesNotExist:
                    errors.append(l)

            if errors or to_many_subscriptions:
                return shortcuts.render(request, 'error.html', {
                        'courses': errors,
                        'max': settings.TIMETABLE_MAX_COURSES,
                        'slug': slug,
                        'year': year,
                        'type': semester_type,
                        'to_many_subscriptions': to_many_subscriptions,
                    })

            return shortcuts.redirect(
                'change-groups', semester.year, semester.type, slug)

        elif 'submit_remove' in request.POST:
            courses = []
            for c in request.POST.getlist('course_remove'):
                if c.strip():
                    courses.append(c.strip())

            Subscription.objects.get_subscriptions(year, semester.type, slug). \
                    filter(course__id__in=courses).delete()

            if Subscription.objects.filter(student__slug=slug).count() == 0:
                Student.objects.filter(slug=slug).delete()

        elif 'submit_name' in request.POST:
            subscriptions = Subscription.objects.get_subscriptions(year, semester.type, slug)

            for u in subscriptions:
                form = CourseAliasForm(request.POST, prefix=u.course_id)

                if form.is_valid():
                    alias = form.cleaned_data['alias'].strip()

                    if alias.upper() == u.course.code.upper() or alias == "":
                        # Leave as blank if we match the current course name
                        alias = ""

                    u.alias = alias
                    u.save()

    return shortcuts.redirect(
        'schedule-advanced', semester.year, semester.type, slug)

def select_lectures(request, year, semester_type, slug):
    '''Handle selection of lectures to hide'''
    semester = Semester(year=year, type=semester_type)

    if request.method == 'POST':
        excludes = request.POST.getlist('exclude')

        subscriptions = Subscription.objects.get_subscriptions(year, semester.type, slug)

        for subscription in subscriptions:
            if excludes:
                subscription.exclude = subscription.course.lecture_set.filter(id__in=excludes)
            else:
                subscription.exclude.clear()

        clear_cache(semester, slug)

    return shortcuts.redirect(
        'schedule-advanced', semester.year, semester.type, slug)

def list_courses(request, year, semester_type, slug):
    '''Display a list of courses'''

    if request.method == 'POST':
        return select_course(request, year, semester_type, slug, add=True)

    semester = Semester(year=year, type=semester_type)
    cache_key = '/'.join([year, semester_type, 'courses'])
    content = request.cache.get(cache_key, realm=False)

    if not content:
        courses = Course.objects.get_courses_with_exams(year, semester.type)

        response = shortcuts.render(request, 'course_list.html', {
                'semester': semester,
                'course_list': courses,
            })

        request.cache.set(cache_key, compress(response.content),
            settings.CACHE_TIME_SCHECULDE, realm=False)

    else:
        response = http.HttpResponse(decompress(content))

    return response

def about(request):
    response = request.cache.get('about', realm=False)
    if response:
        return response
    cursor = connection.cursor()
    cursor.execute('''
        SELECT COUNT(*), date, semester_id FROM (
            SELECT EXTRACT(EPOCH FROM date_trunc('day', min(s.added))) * 1000 AS date,
                s.student_id, c.semester_id
            FROM common_subscription s
            JOIN common_course c ON (c.id = s.course_id)
            GROUP BY s.student_id, c.semester_id
        ) AS foo GROUP BY date, semester_id ORDER by semester_id, date;
        ''')

    last_semester = None
    data = []
    x = 0
    y = 0
    max_x = 0

    for count, date, semester in cursor.fetchall():
        if last_semester != semester:
            last_semester = semester
            x = date - 60*60*24*1000
            y = 0
            data.append([(x,y)])

        x  = int(date)
        y += count

        data[-1].append((x, y))

        if x > max_x:
            max_x = x

    for d in data:
        d.append((max_x, d[-1][1]))

    response = shortcuts.render(request, 'about.html', {
            'data': data,
            'color_map': ColorMap(hex=True)
        })

    request.cache.set('about', response,
        settings.CACHE_TIME_ABOUT, realm=False)

    return response
