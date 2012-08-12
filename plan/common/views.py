# This file is part of the plan timetable generator, see LICENSE for details.

import datetime
import json
import logging

from django import http
from django import shortcuts
from django.conf import settings
from django.db import connection
from django.utils import html
from django.utils import text

from plan.common.models import (Course, Deadline, Exam, Group, Lecture,
    Semester, Subscription, Room, Lecturer, Week, Student)

from plan.common import forms
from plan.common import timetable
from plan.common import utils
from plan.common.templatetags import slugify

# FIXME split into frontpage/semester, course, schedule files
# FIXME Split views that do multiple form handling tasks into seperate views
# that call the top one.

# To allow for overriding of the codes idea of now() for tests
now = datetime.datetime.now

# Start new week on saturdays
get_current_week = lambda: (now() + datetime.timedelta(days=2)).isocalendar()[1]


def frontpage(request):
    try:
        semester = Semester.objects.current()
    except Semester.DoesNotExist:
        raise http.Http404
    return shortcuts.redirect('semester', semester.year, semester.slug)


def shortcut(request, slug):
    '''Redirect users to their timetable for the current semester'''
    try:
        semester = Semester.objects.current()
    except Semester.DoesNotExist:
        raise http.Http404
    return schedule_current(request, semester.year, semester.type, slug)


def getting_started(request, year, semester_type):
    '''Intial top level page that greets users'''
    try:
        semester = Semester.objects.get(year=year, type=semester_type)
    except Semester.DoesNotExist:
        raise http.Http404

    # Redirect user to their timetable
    if request.method == 'POST':
        schedule_form = forms.ScheduleForm(request.POST)

        if schedule_form.is_valid():
            slug = schedule_form.cleaned_data['slug']
            # TODO(adamcik): what should we do if current is empty?
            return schedule_current(request, semester.year, semester.type, slug)
    else:
        schedule_form = forms.ScheduleForm()

    context = Course.get_stats(semester=semester)
    context.update({
        'color_map': utils.ColorMap(hex=True),
        'current': semester,
        'schedule_form': schedule_form,
    })
    return shortcuts.render(request, 'start.html', context)


def course_query(request, year, semester_type):
    limit = min(request.GET.get('limit', '10'), settings.TIMETABLE_AJAX_LIMIT)
    query = request.GET.get('q', '').strip()[:100]

    response = http.HttpResponse(mimetype='text/plain; charset=utf-8')
    if not query:
        return response

    courses = Course.objects.search(year, semester_type, query, limit)

    for course in courses:
        code = html.escape(course.code)
        name = html.escape(text.truncate_words(course.name, 5))
        response.write(u'%s|%s\n' % (code, name or u'?'))

    return response


def schedule_current(request, year, semester_type, slug):
    semester = Semester(year=year, type=semester_type)
    if semester.is_current:
        current_week = get_current_week()

        return shortcuts.redirect(
            'schedule-week', semester.year, semester.slug, slug, current_week)
    return shortcuts.redirect('schedule', semester.year, semester.slug, slug)


def schedule(request, year, semester_type, slug, advanced=False,
             week=None, all=False):
    '''Page that handels showing schedules'''

    current_week = get_current_week()
    if week:
        week = int(week)
        max_week = utils.max_number_of_weeks(year)
    if week is not None:
        if (week <= 0 or week > max_week):
            raise http.Http404

    # Color mapping for the courses
    color_map = utils.ColorMap(hex=True)

    try:  # TODO(adamcik): lookup up to two semesters larger than given ones instead.
        semester = Semester.objects.get(year=year, type=semester_type)
    except Semester.DoesNotExist:
        raise http.Http404

    try:
        student = Student.objects.distinct().get(slug=slug, subscription__course__semester=semester)
    except Student.DoesNotExist:
        student = None

    # Start setting up queries
    courses = Course.objects.get_courses(year, semester.type, slug)
    lectures = Lecture.objects.get_lectures(year, semester.type, slug, week)
    exams = Exam.objects.get_exams(year, semester.type, slug)

    # Use get_related to cut query counts
    lecturers = Lecture.get_related(Lecturer, lectures)
    groups = Lecture.get_related(Group, lectures, fields=['code'])
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
    table = timetable.Timetable(lectures)

    if week:
        table.set_week(semester.year, week)

    if lectures:
        table.place_lectures()
        table.do_expansion()

    table.insert_times()
    table.add_markers()

    if advanced:
        subscriptions = Subscription.objects.get_subscriptions(year, semester.type, slug)

        # Set up and course name forms
        for course in courses:
            alias = course.alias or ''
            course.alias_form = forms.CourseAliasForm(
                initial={'alias': alias}, prefix=course.id)

    next_semester = Semester.current().next()
    if next_semester.year == semester.year and \
            next_semester.type == semester.type:
        next_message = False
    elif not Semester.objects.filter(year=next_semester.year, type=next_semester.type).count():
        next_message = False
    else:
        next_message = Subscription.objects.get_subscriptions(next_semester.year, next_semester.type, slug).count()
        next_message = next_message == 0

    return shortcuts.render(request, 'schedule.html', {
            'advanced': advanced,
            'all': all,
            'color_map': color_map,
            'courses': courses,
            'current': (week == current_week),
            'current_week': current_week,
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


def select_groups(request, year, semester_type, slug):
    '''Form handler for selecting groups to use in schedule'''
    courses = Course.objects.get_courses(year, semester_type, slug)
    course_groups = Course.get_groups(year, semester_type, [c.id for c in courses])

    if request.method == 'POST':
        for c in courses:
            try:
                groups = course_groups[c.id]
            except KeyError: # Skip courses without groups
                continue

            group_form = forms.GroupForm(groups, request.POST, prefix=c.id)

            if group_form.is_valid():
                subscription = Subscription.objects.get_subscriptions(year,
                        semester_type, slug).get(course=c)

                subscription.groups = group_form.cleaned_data['groups']

        return shortcuts.redirect(
            'schedule-advanced', year, Semester.localize(semester_type), slug)

    color_map = utils.ColorMap(hex=True)
    subscription_groups = Subscription.get_groups(year, semester_type, slug)
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

        c.group_form = forms.GroupForm(groups, prefix=c.id, initial={'groups': initial_groups})

    return shortcuts.render(request, 'select_groups.html', {
            'semester': Semester(year=year, type=semester_type),
            'slug': slug,
            'courses': courses,
            'color_map': color_map,
        })


def select_course(request, year, semester_type, slug, add=False):
    '''Handle selecting of courses from course list, change of names and
       removeall of courses'''

    # FIXME split ut three sub functions into seperate functions?

    try:
        semester = Semester.objects.get(year=year, type=semester_type)
    except Semester.DoesNotExist:
        return shortcuts.redirect(
            'schedule', year, Semester.localize(semester_type), slug)

    if request.method == 'POST':
        if 'submit_add' in request.POST or add:
            lookup = []

            for l in request.POST.getlist('course_add'):
                lookup.extend(l.replace(',', '').split())

            subscriptions = set(Subscription.objects.get_subscriptions(year,
                semester_type, slug).values_list('course__code', flat=True))

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
                            semester__year__exact=year,
                            semester__type__exact=semester_type,
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
                'change-groups', year, Semester.localize(semester_type), slug)

        elif 'submit_remove' in request.POST:
            courses = []
            for c in request.POST.getlist('course_remove'):
                if c.strip():
                    courses.append(c.strip())

            Subscription.objects.get_subscriptions(year, semester_type, slug). \
                    filter(course__id__in=courses).delete()

            if Subscription.objects.filter(student__slug=slug).count() == 0:
                Student.objects.filter(slug=slug).delete()

        elif 'submit_name' in request.POST:
            subscriptions = Subscription.objects.get_subscriptions(year, semester_type, slug)

            for u in subscriptions:
                form = forms.CourseAliasForm(request.POST, prefix=u.course_id)

                if form.is_valid():
                    alias = form.cleaned_data['alias'].strip()

                    if alias.upper() == u.course.code.upper() or alias == "":
                        # Leave as blank if we match the current course name
                        alias = ""

                    u.alias = alias
                    u.save()

    return shortcuts.redirect(
        'schedule-advanced', year, Semester.localize(semester_type), slug)


def select_lectures(request, year, semester_type, slug):
    '''Handle selection of lectures to hide'''

    if request.method == 'POST':
        excludes = request.POST.getlist('exclude')

        subscriptions = Subscription.objects.get_subscriptions(year, semester_type, slug)

        for subscription in subscriptions:
            if excludes:
                subscription.exclude = subscription.course.lecture_set.filter(id__in=excludes)
            else:
                subscription.exclude.clear()

    return shortcuts.redirect(
        'schedule-advanced', year, Semester.localize(semester_type), slug)


def list_courses(request, year, semester_type, slug):
    '''Display a list of courses'''

    if request.method == 'POST':
        return select_course(request, year, semester_type, slug, add=True)

    courses = Course.objects.get_courses_with_exams(year, semester_type)
    return shortcuts.render(request, 'course_list.html', {
            'semester': Semester(year=year, type=semester_type),
            'course_list': courses,
        })


def about(request):
    # Limit ourselves to 400 buckets to display within 940px - i.e. 2.3 pixels per sample.
    cursor = connection.cursor()
    cursor.execute('''
        SELECT CAST(EXTRACT(EPOCH FROM MAX(s.added)) -
                    EXTRACT(EPOCH FROM MIN(s.added)) AS INTEGER)
        FROM common_subscription s;''')
    scale = cursor.fetchone()[0] / 400

    # Fetch number of new subcriptions per time bucket:
    cursor.execute('''
        SELECT COUNT(*), bucket, semester_id FROM (
            SELECT
                cast(EXTRACT(EPOCH FROM date_trunc('day', min(s.added))) / %s as integer) AS bucket,
                s.student_id,
                c.semester_id
            FROM common_subscription s
            JOIN common_course c ON (c.id = s.course_id)
            GROUP BY s.student_id, c.semester_id
        ) AS foo GROUP BY bucket, semester_id ORDER by semester_id, bucket;
        ''' % scale)

    last_semester = None
    colors = utils.ColorMap(hex=True)
    fills, series = [], []
    x, y, max_x, first = 0, 0, 0, 0

    # Use zero indexing for x values to keep payload small.
    for count, bucket, semester in cursor.fetchall():
        if not first:
            first = bucket - 1

        if last_semester != semester:
            last_semester = semester
            x, y = (bucket - 1)-first, 0
            series.append([(x,y)])

        x, y = bucket - first, y+count

        series[-1].append((x, y))
        max_x = max(max_x, x)

    for i, s in enumerate(series):
        fills.append(colors[i])
        s.append((max_x, s[-1][1]))

    # Pass on all data we need. First is needed to undo zero indexing, bucket
    # size is needed to rescale x values to proper epochs.
    return shortcuts.render(request, 'about.html', {
            'data':  html.mark_safe(json.dumps({
                'series': series,
                'fills': fills,
                'first': first,
                'scale': scale}, separators=(',',':'))),
        })
