# encoding: utf-8

import logging

from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, Http404
from django.shortcuts import render_to_response, get_list_or_404
from django.template.context import RequestContext
from django.template.defaultfilters import slugify
from django.core.cache import cache
from django.db import connection
from django.db.models import Q
from django.views.generic.list_detail import object_list
from django.conf import settings

from plan.common.models import Course, Deadline, Exam, Group, \
        Lecture, Semester, UserSet, Room, Lecturer, Week
from plan.common.forms import DeadlineForm, GroupForm, CourseNameForm
from plan.common.utils import compact_sequence, ColorMap

def clear_cache(*args):
    """Clears a users cache based on reverse"""

    cache.delete('stats')
    cache.delete(reverse('schedule', args=args))
    cache.delete(reverse('schedule-advanced', args=args))
    cache.delete(reverse('schedule-ical', args=args))
    cache.delete(reverse('schedule-ical-exams', args=args))
    cache.delete(reverse('schedule-ical-lectures', args=args))
    cache.delete(reverse('schedule-ical-deadlines', args=args))

def shortcut(request, slug):
    '''Redirect users to their timetable for the current semester'''

    semester = Semester.current()

    return HttpResponseRedirect(reverse('schedule',
            args = [semester.year, semester.get_type_display(), slug]))

def getting_started(request):
    '''Intial top level page that greets users'''

    semester = Semester.current()

    if request.method == 'POST' and 'slug' in request.POST:
        slug = slugify(request.POST['slug'])

        if slug.strip():
            response = HttpResponseRedirect(reverse('schedule',
                    args = [semester.year, semester.get_type_display(), slug]))

            # Store last timetable visited in a cookie so that we can populate
            # the field with a default value next time.
            response.set_cookie('last', slug, 60*60*24*7*4)
            return response

    context = cache.get('stats')

    if not context or 'no-cache' in request.GET:
        slug_count = int(UserSet.objects.values('slug').distinct().count())
        subscription_count = int(UserSet.objects.count())
        deadline_count = int(Deadline.objects.count())

        stats = []
        color_map = ColorMap(max=settings.MAX_COLORS)
        for i, row in enumerate(Course.get_stats()):
            stats.append(row + (color_map[i],))

        context = {
            'slug_count': slug_count,
            'subscription_count': subscription_count,
            'deadline_count': deadline_count,
            'stats': stats,

        }

        cache.set('stats', context)

    return render_to_response('start.html', context, RequestContext(request))

def schedule(request, year, semester_type, slug, advanced=False, week=None,
        deadline_form=None, cache_page=True):

    '''Page that handels showing schedules'''

    t = request.timer
    response = cache.get(request.path)

    if response and 'no-cache' not in request.GET and cache_page:
        t.tick('Done, returning cache')
        return response

    cursor = connection.cursor()

    # FIXME refactor alogrithm that generates time table to seperate function.

    # Data structure that stores what will become the html table
    table = [[[{}] for a in Lecture.DAYS] for b in Lecture.START]

    # Extra info used to get the table right
    lectures = []

    # Color mapping for the courses
    color_map = ColorMap(max=settings.MAX_COLORS)

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

    # Keep track if all groups are selected for all courses
    all_groups = False

    semester = Semester.get_semester(year, semester_type)

    course_filter = {
        'userset__slug': slug,
        'userset__semester': semester,
    }
    courses = Course.objects.filter(**course_filter). \
        extra(select={'user_name': 'common_userset.name'}).distinct()

    # FIXME rename to lectures, however there is a conflict further down
    initial_lectures = Lecture.objects.get_lectures(slug, semester)

    first_day = semester.get_first_day()
    last_day = semester.get_last_day()

    # FIXME move to static method on Exam?
    exams = Exam.objects.filter(
            exam_date__gt=first_day,
            exam_date__lt=last_day,
            course__userset__slug=slug,
            course__userset__semester=semester,
        ).select_related(
            'course__name',
            'course__full_name',
        ).extra(
            select={'user_name': 'common_userset.name'}
        )

    # FIXME move to static method on Deadline?
    deadlines = Deadline.objects.filter(
            userset__slug=slug,
            userset__semester=semester,
        ).select_related(
            'userset__course',
            'userset__name',
        )

    if not deadline_form and advanced:
        usersets = UserSet.objects.filter(
                slug=slug,
                semester=semester,
            ).select_related(
                'course__name',
            )

        deadline_form = DeadlineForm(usersets)

    t.tick('Done initializing')

    for c in courses:
        c.css_class = color_map[c.id]
    t.tick('Done adding color to course array')

    t.tick('Starting main lecture loop')
    for i, lecture in enumerate(initial_lectures):
        if lecture.exclude:
            continue

        # Our actual layout algorithm for handling collisions and displaying in
        # tables:

        start = lecture.start_time - Lecture.START[0][0]
        end = lecture.end_time - Lecture.END[0][0]
        rowspan = end - start + 1

        first = start

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
            for j in range(len(Lecture.START)):
                table[j][lecture.day].append({})

            # Update the header colspan
            span[lecture.day] += 1

        start = first
        remove = False

        css = [color_map[lecture.course_id], "lecture"]

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
                    'k': row,
                })

            start += 1

    if courses:
        t.tick('Start getting rooms for lecture list')
        rooms = Lecture.helper(Room, initial_lectures)
        t.tick('Done getting rooms for lecture list')

    if courses and advanced:
        for u in UserSet.objects.filter(slug=slug, semester=semester):
            # FIXME need to redefine form to not use Models and querysets

            # SQL: this causes extra queries (can be worked around, subquery?)
            # We can use the same trick as we did for rooms
            initial_groups = u.groups.values_list('id', flat=True)

            # SQL: this causes extra queries (hard to work around, probably not
            # worh it) We can use the same trick as we did for rooms
            course_groups = Group.objects.filter(
                    lecture__course__id=u.course_id
                ).distinct()

            if not all_groups:
                course_groups_ids = course_groups.values_list('id', flat=True)

                if len(course_groups_ids) > 2 and len(initial_groups) > 2:
                    all_groups = set(initial_groups) == set(course_groups_ids)

            # SQL: For loop generates to quries per userset.
            group_forms[u.course_id] = GroupForm(course_groups,
                    initial={'groups': initial_groups}, prefix=u.course_id)

        t.tick('Done creating groups forms')

        groups = Lecture.helper(Group, initial_lectures)
        t.tick('Done getting groups for lecture list')

        lecturers = Lecture.helper(Lecturer, initial_lectures)
        t.tick('Done getting lecturers for lecture list')

        weeks = Lecture.helper(Week, initial_lectures, field='number')
        t.tick('Done getting weeks for lecture list')

    t.tick('Starting lecture expansion')
    for lecture in lectures:
        # Loop over supplementary data structure using this to figure out which
        # colspan expansions are safe
        i = lecture['i']
        j = lecture['j']
        k = lecture['k']

        height = lecture['height']

        expand_by = 1

        r = rooms.get(table[i][j][k]['lecture'].id, [])
        table[i][j][k]['lecture'].sql_rooms = r

        # Find safe expansion of colspan
        safe = True
        for l in xrange(k+1, len(table[i][j])):
            for m in xrange(i, i+height):
                if table[m][j][l]:
                    safe = False
                    break
            if safe:
                expand_by += 1
            else:
                break

        table[i][j][k]['colspan'] = expand_by

        # Remove cells that will get replaced by colspan
        for l in xrange(k+1, k+expand_by):
            for m in xrange(i, i+height):
                table[m][j][l]['remove'] = True
    t.tick('Done with lecture expansion')

    # TODO add second round of expansion equalising colspan

    # Insert extra cell containg times
    times = zip(range(len(Lecture.START)), Lecture.START, Lecture.END)
    for i, start, end in times:
        table[i].insert(0, [{'time': '%s&nbsp;-&nbsp;%s' % \
                (start[1], end[1]), 'class': 'time'}])

    t.tick('Done adding times')

    # Add colors and exlude status
    for lecture in initial_lectures:
        lecture.css_class = color_map[lecture.course_id]

        compact_weeks = compact_sequence(weeks.get(lecture.id, []))

        lecture.sql_weeks = compact_weeks
        lecture.sql_groups = groups.get(lecture.id, [])
        lecture.sql_lecturers = lecturers.get(lecture.id, [])
        lecture.sql_rooms = rooms.get(lecture.id, [])

    if advanced:
        for course in courses:
            course.group_form = group_forms.get(c.id, None)
            course.name_form = CourseNameForm(initial={'name': c.user_name or ''}, prefix=c.id)

        t.tick('Done lecture css_clases and excluded status')

    # FIXME replace these loops with a template tag ;)
    for exam in exams:
        exam.css_class = color_map[exam.course_id]

    for deadline in deadlines:
        deadline.css_class = color_map[deadline.userset.course_id]

    t.tick('Starting render to response')
    response = render_to_response('schedule.html', {
            'advanced': advanced,
            'colspan': span,
            'courses': courses,
            'deadline_form': deadline_form,
            'deadlines': deadlines,
            'exams': exams,
            'group_help': all_groups,
            'lectures': initial_lectures,
            'semester': semester,
            'slug': slug,
            'table': table,
        }, RequestContext(request))

    if cache_page:
        t.tick('Saving to cache')

        if deadlines:
            cache_time = deadlines[0].get_seconds()
        else:
            cache_time = settings.CACHE_TIME

        cache.set(request.path, response, cache_time)

    t.tick('Returning repsonse')
    return response

def select_groups(request, year, semester_type, slug):
    '''Form handler for selecting groups to use in schedule'''

    semester = Semester.get_semester(year, semester_type)

    if request.method == 'POST':
        course_filter = {'userset__slug': slug}
        courses = Course.objects.filter(**course_filter).\
                distinct().order_by('id')

        for c in courses:
            groups = Group.objects.filter(lecture__course=c).distinct()
            group_form = GroupForm(groups, request.POST, prefix=c.id)

            if group_form.is_valid():
                userset = UserSet.objects.get(
                        course=c,
                        slug=slug,
                        semester=semester
                    )
                userset.groups = group_form.cleaned_data['groups']

        clear_cache(year, semester.get_type_display(), slug)

        logging.debug('Deleted cache')

    return HttpResponseRedirect(reverse('schedule-advanced',
            args=[semester.year,semester.get_type_display(),slug]))

def new_deadline(request, year, semester_type, slug):
    '''Handels addition of tasks, reshows schedule view if form does not
       validate'''
    semester = Semester.get_semester(year, semester_type)

    if request.method == 'POST':
        clear_cache(year, semester.get_type_display(), slug)
        logging.debug('Deleted cache')

        post = request.POST.copy()

        if 'submit_add' in post and 'submit_remove' in post:
            # IE6 doesn't handle <button> correctly, it submits all buttons
            if 'deadline_remove' in post:
                # User has checked at least on deadline to remove, make a blind
                # guess and remove submit_add button.
                del post['submit_add']

        if 'submit_add' in post:
            usersets = UserSet.objects.filter(slug=slug, semester=semester)
            deadline_form = DeadlineForm(usersets, post)

            if deadline_form.is_valid():
                deadline_form.save()
            else:
                return schedule(request, year, semester_type, slug, advanced=True,
                        deadline_form=deadline_form, cache_page=False)

        elif 'submit_remove' in post:
            Deadline.objects.filter(
                    id__in=post.getlist('deadline_remove')
                ).delete()

    return HttpResponseRedirect(reverse('schedule-advanced',
            args = [semester.year,semester.get_type_display(),slug]))

def copy_deadlines(request, year, semester_type, slug):
    '''Handles importing of deadlines'''

    semester = Semester.get_semester(year, semester_type)

    if request.method == 'POST':
        if 'slugs' in request.POST:
            slugs = request.POST['slugs'].replace(',', ' ').split()

            color_map = ColorMap(max=settings.MAX_COLORS)

            courses = Course.objects.filter(
                    userset__slug=slug,
                    userset__semester=semester,
                ).distinct()

            # Init color map
            for c in courses:
                color_map[c.id]

            deadlines = Deadline.objects.filter(
                    userset__slug__in=slugs,
                    userset__semester=semester,
                    userset__course__in=courses,
                ).select_related(
                    'userset__course__id'
                ).exclude(userset__slug=slug)

            for d in deadlines:
                d.css_class = color_map[d.userset.course_id]

            return render_to_response('select_deadlines.html', {
                    'deadlines': deadlines,
                    'semester': semester,
                    'slug': slug,
                }, RequestContext(request))

        elif 'deadline_id' in request.POST:
            deadline_id = request.POST.getlist('deadline_id')
            deadlines = Deadline.objects.filter(id__in=deadline_id)

            for d in deadlines:
                userset = UserSet.objects.get(
                        slug=slug,
                        semester=semester,
                        course=d.userset.course
                )
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

    semester = Semester.get_semester(year, semester_type)

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

            # FIXME limit max courses to for instance 30

            for l in lookup:
                try:
                    course = Course.objects.get(
                            name__iexact=l.strip(),
                            semesters__in=[semester]
                        )
                    userset, created = UserSet.objects.get_or_create(
                            slug=slug,
                            course=course,
                            semester=semester
                        )

                    groups = Group.objects.filter(
                            lecture__course=course
                        ).distinct()
                    for g in groups:
                        userset.groups.add(g)

                except Course.DoesNotExist:
                    errors.append(l)

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

            sets = UserSet.objects.filter(
                    slug__iexact=slug,
                    course__id__in=courses
                )
            sets.delete()

        elif 'submit_name' in post:
            userset_filter = {
                'slug': slug,
                'semester': semester,
            }
            userset_related = [
                'course__name',
            ]

            usersets = UserSet.objects.filter(**userset_filter). \
                            select_related(*userset_related)

            for u in usersets:
                form = CourseNameForm(post, prefix=u.course_id)
                logging.debug("Checking %s" % u)

                if form.is_valid():
                    logging.debug("Form for %s is valid" % u)

                    name = form.cleaned_data['name'].strip()

                    if name.upper() == u.course.name.upper() or name == "":
                        # Leave as blank if we match the current course name
                        name = ""

                    u.name = name

                    logging.debug("Saving %s as %s" % (u.course.name, name))
                    u.save()
                else:
                    logging.debug("Form for %s is invalid" % u)

    return HttpResponseRedirect(reverse('schedule-advanced',
            args=[semester.year, semester.get_type_display(), slug]))

def select_lectures(request, year, semester_type, slug):
    '''Handle selection of lectures to hide'''
    semester = Semester.get_semester(year, semester_type)

    if request.method == 'POST':
        excludes = request.POST.getlist('exclude')

        userset_filter = {
            'slug': slug,
            'semester': semester,
        }

        for userset in UserSet.objects.filter(**userset_filter):
            userset.exclude = userset.course.lecture_set.filter(id__in=excludes)

        clear_cache(semester.year, semester.get_type_display(), slug)

        logging.debug('Deleted cache')

    return HttpResponseRedirect(reverse('schedule-advanced',
            args=[semester.year, semester.get_type_display(), slug]))

def list_courses(request, year, semester, slug):
    '''Display a list of courses based on when exam is'''

    if request.method == 'POST':
        return select_course(request, year, semester, slug, add=True)

    response = cache.get('course_list')

    if not response:
        semester = Semester.get_semester(year, semester)

        first_day = semester.get_first_day()
        last_day = semester.get_last_day()

        no_exam = Q(exam__isnull=True)
        with_exam = Q(exam__exam_date__gt=first_day, exam__exam_date__lt=last_day)

        courses = Course.objects.filter(semesters__in=[semester]). \
            filter(no_exam | with_exam).extra(select={
                'exam_date': 'common_exam.exam_date',
                'exam_time': 'common_exam.exam_time',
                'handout_date': 'common_exam.handout_date',
                'handout_time': 'common_exam.handout_time',
                'type': 'common_exam.type',
                'type_name': 'common_exam.type_name',
            })

        response = object_list(request,
                courses,
                extra_context={'semester': semester},
                template_object_name='course',
                template_name='course_list.html')

        cache.set('course_list', response)

    return response
