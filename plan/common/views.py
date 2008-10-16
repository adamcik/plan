# encoding: utf-8

import logging

from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, Http404
from django.shortcuts import render_to_response, get_list_or_404
from django.template.context import RequestContext
from django.template.defaultfilters import slugify
from django.core.cache import cache
from django.db import connection
from django.views.generic.list_detail import object_list
from django.conf import settings

from plan.common.models import Course, Deadline, Exam, Group, \
        Lecture, Semester, UserSet
from plan.common.forms import DeadlineForm, GroupForm, CourseNameForm
from plan.common.utils import compact_sequence

MAX_COLORS = 8

def clear_cache(*args):
    """Clears a users cache based on reverse"""

    cache.delete('stats')
    cache.delete(reverse('schedule', args=args))
    cache.delete(reverse('schedule-advanced', args=args))
    cache.delete(reverse('schedule-ical', args=args))
    cache.delete(reverse('schedule-ical-exams', args=args))
    cache.delete(reverse('schedule-ical-lectures', args=args))
    cache.delete(reverse('schedule-ical-deadlines', args=args))

def get_semester(year, semester):
    """Utility method to help retrive semesters"""

    try:
        semester_map = dict(map(lambda x: (x[1], x[0]), Semester.TYPES))
        semester = semester_map[semester.lower()]

        return Semester.objects.get(year=year, type=semester)
    except (KeyError, Semester.DoesNotExist):
        raise Http404

def get_lectures(slug, semester):
    """
        Get all lectures for userset during given period.

        To do this we need to pull in a bunch of extra tables and manualy join them
        in the where cluase. The first element in the custom where is the important
        one that limits our results, the rest are simply meant for joining.
    """
    # FIXME this should be part of a custom manger

    where = [
        'common_userset_groups.group_id = common_group.id',
        'common_userset_groups.userset_id = common_userset.id',
        'common_group.id = common_lecture_groups.group_id',
        'common_lecture_groups.lecture_id = common_lecture.id'
    ]
    tables = [
        'common_userset_groups',
        'common_group',
        'common_lecture_groups'
    ]
    select = {
        'user_name': 'common_userset.name',
        'exclude': """common_lecture.id IN
            (SELECT common_userset_exclude.lecture_id
             FROM common_userset_exclude WHERE
             common_userset_exclude.userset_id = common_userset.id)""",
    }

    filter = {
        'course__userset__slug': slug,
        'course__userset__semester': semester,
    }

    related = [
        'type__name',
        'course__name',
    ]

    order = [
        'course__name',
        'day',
        'start_time',
        'type__name',
    ]

    return  Lecture.objects.filter(**filter).\
                distinct().\
                select_related(*related).\
                extra(where=where, tables=tables, select=select).\
                order_by(*order)

def shortcut(request, slug):
    get_list_or_404(UserSet, slug=slug)

    # FIXME .current should be on a manager
    semester = Semester.current()

    return HttpResponseRedirect(reverse('schedule',
            args = [semester.year, semester.get_type_display(), slug]))

def getting_started(request):
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

    if not context:
        limit = 20

        cursor = connection.cursor()
        cursor.execute('''
            SELECT COUNT(*) as num, c.name, c.full_name FROM
                common_userset u JOIN common_course c ON (c.id = u.course_id)
            GROUP BY c.name, c.full_name
            ORDER BY num DESC
            LIMIT %d''' % limit)

        slug_count = int(UserSet.objects.values('slug').distinct().count())
        subscription_count = int(UserSet.objects.count())
        deadline_count = int(Deadline.objects.count())

        context = {
            'slug_count': slug_count,
            'subscription_count': subscription_count,
            'deadline_count': deadline_count,
            'stats': cursor.fetchall(),

        }

        cache.set('stats', context)

    return render_to_response('start.html', context, RequestContext(request))

def schedule(request, year, semester, slug, advanced=False, week=None,
        deadline_form=None, cache_page=True):

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

    exam_list = Exam.objects.filter(
            exam_date__gt=first_day,
            exam_date__lt=last_day,
            course__userset__slug=slug,
            course__userset__semester=semester,
        ).select_related(
            'course__name',
            'course__full_name',
        )

    deadlines = Deadline.objects.filter(
            userset__slug=slug,
            userset__semester=semester,
        ).select_related(
            'userset__course',
        )

    if not deadline_form:
        usersets = UserSet.objects.filter(
                slug=slug,
                semester=semester,
            ).select_related(
                'course__name',
            )

        deadline_form = DeadlineForm(usersets)

    t.tick('Done initializing')

    course_filter = {
        'userset__slug': slug,
        'userset__semester': semester,
    }
    course_select = {
        'user_name': 'common_userset.name',
    }
    for c in Course.objects.filter(**course_filter).extra(select=course_select).distinct():
        # Create an array containing our courses and add the css class
        if c.id not in color_map:
            color_index = (color_index + 1) % MAX_COLORS
            color_map[c.id] = 'lecture%d' % color_index

        c.css_class = color_map[c.id]

        courses.append((c, None))

        t.tick('Added course %s' % c.name)

    t.tick('Done building course array')

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
            for j, time in enumerate(Lecture.START):
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

    # Compute where clause that limits the size of the following queries
    lecture_id_where_clause = 'lecture_id IN (%s)' % \
            ','.join([str(l.id) for l in initial_lectures])

    if courses:
        t.tick('Start getting rooms for lecture list')
        cursor.execute('''SELECT common_lecture_rooms.lecture_id,
                common_room.name FROM common_lecture_rooms
                INNER JOIN common_room
                    ON (common_room.id = common_lecture_rooms.room_id)
                WHERE %s''' % lecture_id_where_clause)

        for lecture_id, name in cursor.fetchall():
            if lecture_id not in rooms:
                rooms[lecture_id] = []

            rooms[lecture_id].append(name)
    t.tick('Done getting rooms for lecture list')

    if advanced and courses:
        for u in UserSet.objects.filter(slug=slug, semester=semester):
            # SQL: this causes extra queries (can be worked around, subquery?)
            initial_groups = u.groups.values_list('id', flat=True)

            # SQL: this causes extra queries (hard to work around, probably not
            # worh it)
            course_groups = Group.objects.filter(
                    lecture__course__id=u.course_id
                ).distinct()

            # SQL: For loop generates to quries per userset.
            group_forms[u.course_id] = GroupForm(course_groups,
                    initial={'groups': initial_groups}, prefix=u.course_id)

        t.tick('Done creating groups forms')

        # Do three custom sql queries to prevent and explosion of sql queries
        # due to ORM. FIXME do same queries using ORM
        cursor.execute('''SELECT common_lecture_groups.lecture_id,
                common_group.name FROM common_lecture_groups
                INNER JOIN common_group ON
                    (common_group.id = common_lecture_groups.group_id)
                WHERE %s''' % lecture_id_where_clause)

        for lecture_id, name in cursor.fetchall():
            if lecture_id not in groups:
                groups[lecture_id] = []

            groups[lecture_id].append(name)
        t.tick('Done getting groups for lecture list')

        cursor.execute('''SELECT common_lecture_lecturers.lecture_id,
                common_lecturer.name FROM common_lecture_lecturers
                INNER JOIN common_lecturer
                    ON (common_lecturer.id = common_lecture_lecturers.lecturer_id)
                WHERE %s''' % lecture_id_where_clause)

        for lecture_id, name in cursor.fetchall():
            if lecture_id not in lecturers:
                lecturers[lecture_id] = []

            lecturers[lecture_id].append(name)

        t.tick('Done getting lecturers for lecture list')

        cursor.execute('''SELECT common_lecture_weeks.lecture_id,
                common_week.number FROM common_lecture_weeks
                INNER JOIN common_week
                    ON (common_week.id = common_lecture_weeks.week_id)
                WHERE %s''' % lecture_id_where_clause)

        for lecture_id, name in cursor.fetchall():
            if lecture_id not in weeks:
                weeks[lecture_id] = []

            weeks[lecture_id].append(name)

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
    if advanced:
        for i, lecture in enumerate(initial_lectures):
            initial_lectures[i].css_class = color_map[lecture.course_id]

            compact_weeks = compact_sequence(weeks.get(lecture.id, []))

            initial_lectures[i].sql_weeks = compact_weeks
            initial_lectures[i].sql_groups = groups.get(lecture.id, [])
            initial_lectures[i].sql_lecturers = lecturers.get(lecture.id, [])
            initial_lectures[i].sql_rooms = rooms.get(lecture.id, [])

        for i, c in enumerate(courses):
            # FIXME cleanup use of tuple
            courses[i] = (c[0], group_forms.get(c[0].id, None))

            # FIXME Loop usersets instead of courses
            name = c[0].user_name or c[0].name
            courses[i][0].name_form = CourseNameForm(initial={'name': name}, prefix=c[0].id)

        t.tick('Done lecture css_clases and excluded status')

    for i, exam in enumerate(exam_list):
        exam_list[i].css_class = color_map[exam.course_id]

    for i, deadline in enumerate(deadlines):
        deadlines[i].css_class = color_map[deadline.userset.course_id]

    t.tick('Starting render to response')
    response = render_to_response('schedule.html', {
            'advanced': advanced,
            'colspan': span,
            'courses': courses,
            'deadlines': deadlines,
            'deadline_form': deadline_form,
            'exams': exam_list,
            'lectures': initial_lectures,
            'legend': map(lambda x: x[0], courses),
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

def select_groups(request, year, type, slug):
    semester = get_semester(year, type)

    if request.method == 'POST':
        course_filter = {'userset__slug': slug}
        courses = Course.objects.filter(**course_filter).\
                distinct().order_by('id')

        for c in courses:
            groups = Group.objects.filter(lecture__course=c).distinct()
            group_form = GroupForm(groups, request.POST, prefix=c.id)

            if group_form.is_valid():
                set = UserSet.objects.get(
                        course=c,
                        slug=slug,
                        semester=semester
                    )
                set.groups = group_form.cleaned_data['groups']

        clear_cache(year, semester.get_type_display(), slug)

        logging.debug('Deleted cache')

    return HttpResponseRedirect(reverse('schedule-advanced',
            args=[semester.year,semester.get_type_display(),slug]))

def new_deadline(request, year, type, slug):
    semester = get_semester(year, type)

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
                return schedule(request, year, type, slug, advanced=True,
                        deadline_form=deadline_form, cache_page=False)

        elif 'submit_remove' in post:
            Deadline.objects.filter(
                    id__in=post.getlist('deadline_remove')
                ).delete()

    return HttpResponseRedirect(reverse('schedule-advanced',
            args = [semester.year,semester.get_type_display(),slug]))

def copy_deadlines(request, year, type, slug):
    semester = get_semester(year, type)

    if request.method == 'POST':
        if 'slugs' in request.POST:
            slugs = request.POST['slugs'].replace(',', ' ').split()

            color_map = {}
            color_index = 0

            courses = Course.objects.filter(
                    userset__slug=slug,
                    userset__semester=semester,
                ).distinct()

            for c in courses:
                # Create an array containing our courses and add the css class
                if c.id not in color_map:
                    color_index = (color_index + 1) % MAX_COLORS
                    color_map[c.id] = 'lecture%d' % color_index

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

def select_course(request, year, type, slug, add=False):
    semester = get_semester(year, type)

    if request.method == 'POST':

        clear_cache(year, semester.get_type_display(), slug)

        post = request.POST.copy()

        if 'submit_add' in post and 'submit_remove' in post and 'submit_name' in post:
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

            usersets = UserSet.objects.filter(**userset_filter).select_related(*userset_related)

            for u in usersets:
                form = CourseNameForm(post, prefix=u.course_id)
                logging.debug("Checking %s" % u)

                if form.is_valid():
                    logging.debug("Form for %s is valid" % u)

                    name = form.cleaned_data['name']

                    if name != u.course.name:
                        # We don't check for empty strings as that equals not set
                        logging.debug("Saving %s as %s" % (u.course.name, name))
                        u.name = name
                        u.save()
                else:
                    logging.debug("Form for %s is invalid" % u)

    return HttpResponseRedirect(reverse('schedule-advanced',
            args=[semester.year, semester.get_type_display(), slug]))

def select_lectures(request, year, type, slug):
    if request.method == 'POST':
        excludes = request.POST.getlist('exclude')

        userset_filter = {
            'slug': slug,
            'semester__type': type,
            'semester__year': year,
        }

        for userset in UserSet.objects.filter(**userset_filter):
            userset.exclude = userset.course.lecture_set.filter(id__in=excludes)

        clear_cache(year, type, slug)

        logging.debug('Deleted cache')

    return HttpResponseRedirect(reverse('schedule-advanced',
            args=[year,type,slug]))

def list_courses(request, year, semester, slug):
    if request.method == 'POST':
        return select_course(request, year, semester, slug, add=True)


    response = cache.get('course_list')

    if not response:
        semester = get_semester(year, semester)

        first_day = semester.get_first_day()
        last_day = semester.get_last_day()

        exams = Exam.objects.filter(
                exam_date__gt=first_day,
                exam_date__lt=last_day,
                course__semesters__in=[semester]
            ).select_related(
                'course__name',
                'course__full_name'
            ).order_by(
                'course__name',
                'handout_date',
                'exam_date'
            )

        response = object_list(request,
                exams,
                extra_context={'semester': semester},
                template_object_name='exam',
                template_name='course_list.html')

        cache.set('course_list', response)

    return response
