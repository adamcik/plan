# encoding: utf-8

import logging
from time import time

from django.conf import settings
from django.core.cache import cache
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response
from django.template.context import RequestContext
from django.template.defaultfilters import slugify
from django.views.generic.list_detail import object_list

from plan.common.models import Course, Deadline, Exam, Group, \
        Lecture, Semester, UserSet, Room, Lecturer, Week
from plan.common.forms import DeadlineForm, GroupForm, CourseNameForm, \
        ScheduleForm
from plan.common.utils import compact_sequence, ColorMap
from plan.common.timetable import Timetable

# FIXME, handle with signals
from plan.pdf.views import clear_cache as clear_pdf_cache

# FIXME Split views that do multiple form handling tasks into seperate views
# that call the top one.

# FIXME, handle with signals
def clear_cache(*args):
    """Clears a users cache based on reverse"""

    args = list(args)

    # FIXME this does not seem to work for stats
    cache.delete('stats-%s-%s' % (args[0], args[1]))
    cache.delete(reverse('schedule', args=args))
    cache.delete(reverse('schedule-advanced', args=args))
    cache.delete(reverse('schedule-ical', args=args))
    cache.delete(reverse('schedule-ical-exams', args=args))
    cache.delete(reverse('schedule-ical-lectures', args=args))
    cache.delete(reverse('schedule-ical-deadlines', args=args))

    for w in Semester().get_weeks():
        cache.delete(reverse('schedule-week', args=args+[w]))

    cache.delete('%s-group_help' % reverse('schedule', args=args))

    logging.debug('Deleted common cache')

    clear_pdf_cache(*args)

def shortcut(request, slug):
    '''Redirect users to their timetable for the current semester'''

    semester = Semester.current()

    return HttpResponseRedirect(reverse('schedule',
            args = [semester.year, semester.get_type_display(), slug.strip()]))

def getting_started(request, year=None, semester_type=None):
    '''Intial top level page that greets users'''
    schedule_form = None

    if year and semester_type:
        semester = Semester(year=year, type=semester_type)
    else:
        semester = Semester.current()

    # Redirect user to their timetable
    if request.method == 'POST' and 'slug' in request.POST:
        schedule_form = ScheduleForm(request.POST)

        if schedule_form.is_valid():
            slug = slugify(schedule_form.cleaned_data['slug'])
            semester = schedule_form.cleaned_data['semester'] or \
                Semester.current()

            if slug.strip():
                response = HttpResponseRedirect(reverse('schedule', args=[
                    semester.year, semester.get_type_display(), slug]))

                # Store last timetable visited in a cookie so that we can populate
                # the field with a default value next time.
                response.set_cookie('last', slug, 60*60*24*7*4)
                return response

    context = cache.get('stats-%s-%s' % (semester.year, semester.type))

    if not context or 'no-cache' in request.GET:
        try:
            semester = Semester.objects.get(year=semester.year, type=semester.type)
        except Semester.DoesNotExist:
            return HttpResponseRedirect('/')

        if not schedule_form:
            schedule_form = ScheduleForm(initial={'semester': semester.id,
                'slug': '%s'})

        slug_count = int(UserSet.objects.filter(semester__in=[semester]). \
                values('slug').distinct().count())

        subscription_count = int(UserSet.objects.filter(semester__in=\
                [semester]).count())

        deadline_count = int(Deadline.objects.filter(userset__semester__in=\
                [semester]).count())

        context = {
            'color_map': ColorMap(),
            'current': semester,
            'slug_count': slug_count,
            'subscription_count': subscription_count,
            'deadline_count': deadline_count,
            'stats': Course.get_stats(semester=semester),
            'schedule_form': '\n'.join([str(f) for f in schedule_form]),
        }

        cache.set('stats-%s-%s' % (semester.year, semester.type), context, 3*60)

    context['schedule_form'] = context['schedule_form'] % request.COOKIES.get('last', '')

    return render_to_response('start.html', context, RequestContext(request))

def schedule(request, year, semester_type, slug, advanced=False,
        week=None, deadline_form=None, cache_page=True):
    '''Page that handels showing schedules'''

    response = cache.get(request.path)

    if response and 'no-cache' not in request.GET and cache_page:
        return response

    # Color mapping for the courses
    color_map = ColorMap()

    group_forms = {}

    semester = Semester(year=year, type=semester_type)

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

    # Init colors in predictable maner
    for c in courses:
        color_map[c.id]

    # Create Timetable
    table = Timetable(lectures, rooms)
    if lectures:
        table.place_lectures()
        table.do_expansion()
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

    group_help = '%s-group_help' % reverse('schedule',
            args=[year, semester.get_type_display(), slug])

    group_help = cache.get(group_help, 0)

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
        }, RequestContext(request))

    if cache_page:
        if deadlines:
            cache_time = deadlines[0].get_seconds()
        else:
            cache_time = settings.CACHE_TIME

        logging.debug('Group help time: %s, current time: %s, diff %s' %
            (group_help, time(), group_help - time()))
        group_help -= time()
        if group_help > 0:
            cache_time = group_help

        logging.debug('Cache time: %.2f min' % (cache_time / 60))

        cache.set(request.path, response, cache_time)
    return response

def select_groups(request, year, semester_type, slug):
    '''Form handler for selecting groups to use in schedule'''

    semester = Semester(year=year, type=semester_type)

    if request.method == 'POST':
        courses = Course.objects.get_courses(year, semester.type, slug)

        course_groups = Course.get_groups(year, semester.type, [c.id for c in courses])

        for c in courses:
            groups = course_groups[c.id]
            group_form = GroupForm(groups, request.POST, prefix=c.id)

            if group_form.is_valid():
                userset = UserSet.objects.get_usersets(year,
                        semester.type, slug).get(course=c)

                userset.groups = group_form.cleaned_data['groups']

        clear_cache(year, semester.get_type_display(), slug)

    return HttpResponseRedirect(reverse('schedule-advanced',
            args=[semester.year,semester.get_type_display(),slug]))

def new_deadline(request, year, semester_type, slug):
    '''Handels addition of tasks, reshows schedule view if form does not
       validate'''
    semester = Semester(year=year, type=semester_type)

    if request.method == 'POST':
        clear_cache(year, semester.get_type_display(), slug)

        post = request.POST.copy()

        if 'submit_add' in post and 'submit_remove' in post:
            # IE6 doesn't handle <button> correctly, it submits all buttons
            if 'deadline_remove' in post:
                # User has checked at least on deadline to remove, make a blind
                # guess and remove submit_add button.
                del post['submit_add']

        if 'submit_add' in post:
            usersets = UserSet.objects.get_usersets(year, semester.type, slug)
            deadline_form = DeadlineForm(usersets, post)

            if deadline_form.is_valid():
                deadline_form.save()
            else:
                return schedule(request, year, semester_type, slug, advanced=True,
                        deadline_form=deadline_form, cache_page=False)

        elif 'submit_remove' in post:
            logging.debug(post.getlist('deadline_remove'))
            Deadline.objects.get_deadlines(year, semester.type, slug).filter(
                    id__in=post.getlist('deadline_remove')
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
            clear_cache(year, semester.get_type_display(), slug)

    return HttpResponseRedirect(reverse('schedule',
            args=[semester.year,semester.get_type_display(),slug]))

def select_course(request, year, semester_type, slug, add=False):
    '''Handle selecting of courses from course list, change of names and
       removeall of courses'''

    # FIXME split ut three sub functions into seperate functions?

    semester = Semester(type=semester_type)
    try:
        semester = Semester.objects.get(year=year, type=semester.type)
    except Semester.DoesNotExist:
        return HttpResponseRedirect(reverse('schedule', args=
                [year,semester.get_type_display(),slug]))

    if request.method == 'POST':

        clear_cache(year, semester.get_type_display(), slug)

        post = request.POST.copy()

        if 'submit_add' in post and 'submit_remove' in post and \
                'submit_name' in post:
            # IE6 doesn't handle <button> correctly, it submits all buttons
            if 'course_remove' in post:
                # User has checked at least on course to remove, make a blind
                # guess and remove submit_add button.
                del post['submit_add']
                del post['submit_name']
            else:
                if post['course_add'].strip():
                    # Someone put something in course add box, assumme thats
                    # what they want to do
                    del post['submit_remove']
                    del post['submit_name']
                else:
                    del post['submit_remove']
                    del post['submit_add']

        if 'submit_add' in post or add:
            lookup = []

            for l in post.getlist('course_add'):
                lookup.extend(l.replace(',', '').split())

            errors = []
            max_group_count = 0

            # FIXME limit max courses to for instance 30

            for l in lookup:
                try:
                    course = Course.objects.get(
                            name__iexact=l.strip(),
                            semesters__in=[semester],
                        )
                    userset, created = UserSet.objects.get_or_create(
                            slug=slug,
                            course=course,
                            semester=semester
                        )

                    groups = Group.objects.filter(
                            lecture__course=course
                        ).distinct()

                    group_count = 0
                    for g in groups:
                        userset.groups.add(g)
                        group_count += 1

                    if group_count > max_group_count:
                        max_group_count = group_count

                except Course.DoesNotExist:
                    errors.append(l)

            if UserSet.objects.get_usersets(year, semester.type, slug).count() > 20:
                logging.warning("%s has more than 20 courses." % request.path)

            if max_group_count > 2:
                group_help = '%s-group_help' % reverse('schedule',
                        args=[year, semester.get_type_display(), slug])
                cache.set(group_help, int(time())+60*10, 60*10)

            if errors:
                return render_to_response('error.html', {
                        'courses': errors,
                        'slug': slug,
                        'year': year,
                        'type': semester.get_type_display()
                    }, RequestContext(request))

        elif 'submit_remove' in post:
            courses = []
            for c in post.getlist('course_remove'):
                if c.strip():
                    courses.append(c.strip())

            UserSet.objects.get_usersets(year, semester.type, slug). \
                    filter(course__id__in=courses).delete()

        elif 'submit_name' in post:
            usersets = UserSet.objects.get_usersets(year, semester.type, slug)

            for u in usersets:
                form = CourseNameForm(post, prefix=u.course_id)

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
            userset.exclude = userset.course.lecture_set.filter(id__in=excludes)

        clear_cache(semester.year, semester.get_type_display(), slug)

    return HttpResponseRedirect(reverse('schedule-advanced',
            args=[semester.year, semester.get_type_display(), slug]))

def list_courses(request, year, semester_type, slug):
    '''Display a list of courses based on when exam is'''

    if request.method == 'POST':
        return select_course(request, year, semester_type, slug, add=True)

    response = cache.get(''.join(request.path.split('/')[:-2]))

    if not response:
        semester = Semester(year=year, type=semester_type)

        courses = Course.objects.get_courses_with_exams(year, semester.type)

        response = render_to_response('course_list.html', {
                'semester': semester,
                'course_list': courses,
            }, RequestContext(request))

        cache.set(''.join(request.path.split('/')[:-2]), response)

    return response
