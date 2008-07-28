# encoding: utf-8

import re
from datetime import datetime
from urllib import urlopen, quote as urlquote
from BeautifulSoup import BeautifulSoup, NavigableString

from django.shortcuts import get_object_or_404, render_to_response
from django.template.context import RequestContext
from django.http import HttpResponseRedirect, HttpResponse, Http404
from django.core.urlresolvers import reverse, NoReverseMatch
from django.db.models import Q
from django.template.defaultfilters import slugify

from plan.common.models import *
from plan.common.forms import *

MAX_COLORS = 8

def getting_started(request):
    if request.method == 'POST' and 'slug' in request.POST:
        slug = slugify(request.POST['slug'])

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
    return render_to_response('common/start.html', {}, RequestContext(request))

def schedule(request, year, semester, slug, advanced=False):
    # Data structure that stores what will become the html table
    table = [[[{}] for a in Lecture.DAYS] for b in Lecture.START]

    # Extra info used to get the table right
    lectures = []

    # ids of included lectures
    included = []

    # Color mapping for the courses
    color_map = {}
    color_index = 0

    # Array with courses to show
    courses = []

    # Default to current year
    if not year:
        year = datetime.now().year

    # Default to current semester
    semester = dict(map(lambda x: (x[1],x[0]), Semester.TYPES))[semester.lower()]
    semester = Semester.objects.get(year=year, type=semester)

    # Get all lectures for userset during given period. To do this we need to
    # pull in a bunch of extra tables and manualy join them in the where
    # cluase. The first element in the custom where is the important one that
    # limits our results, the rest are simply meant for joining.
    # FIXME convert the first where clause to a select boolean
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

    filter = {
        'course__userset__slug': slug,
        'course__userset__semester': semester,
    }

    # Courses to highlight
    highlight = request.GET.get('highlight', '').split(',')

    initial_lectures = Lecture.objects.filter(**filter).distinct().select_related().extra(where=where, tables=tables).order_by('course__name', 'day', 'start_time', 'type')

    for c in Course.objects.filter(userset__slug=slug, lecture__semester=semester).distinct():
        groups = c.userset_set.get(slug=slug).groups.values_list('id', flat=True)
        group_form = GroupForm(Group.objects.filter(lecture__course=c).distinct(), initial={'groups': groups}, prefix=c.id)

        if c.id not in color_map:
            color_index = (color_index + 1) % MAX_COLORS
            color_map[c.id] = 'lecture%d' % color_index

        c.css_class = color_map[c.id]

        courses.append([c, group_form])

    for i,lecture in enumerate(initial_lectures.exclude(excluded_from__slug=slug)):
        start = lecture.start_time - Lecture.START[0][0]
        end = lecture.end_time - Lecture.END[0][0]
        rowspan = end - start + 1

        first = start

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

        start = first
        remove = False

        # Set the css class for the color map
        if lecture.course_id not in color_map:
            color_index = (color_index + 1) % MAX_COLORS
            color_map[lecture.course_id] = 'lecture%d' % color_index

        css = [color_map[lecture.course_id]]

        if lecture.type.optional:
            css.append('optional')

        if rowspan == 1:
            css.append('single')

        if str(lecture.course_id) in highlight:
            css.append('highlight')

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
                    'lecture': lecture,
                    'height': rowspan,
                    'i': start,
                    'j': lecture.day,
                    'm': row,
                })

            start += 1

    for lecture in lectures:
        # Loop over supplementary data structure
        i = lecture['i']
        j = lecture['j']
        m = lecture['m']
        height = lecture['height']

        expand_by = 1

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

    # Calculate the header colspan
    span = [1] * 5
    for i,cell in enumerate(table[0]):
        span[i] = len(cell)

    # Insert extra cell containg times
    for t,start,end in map(lambda x,y: (x[0], x[1][1],y[1]), enumerate(Lecture.START), Lecture.END):
        table[t].insert(0, [{'time': '%s - %s' % (start, end), 'class': 'time'}])

    # Add colors and exlude status
    for i,lecture in enumerate(initial_lectures):
        initial_lectures[i].css_class =  color_map[lecture.course_id]
        initial_lectures[i].excluded  =  lecture.id not in included


    return render_to_response('common/schedule.html', {
                            'advanced': advanced,
                            'colspan': span,
                            'courses': courses,
                            'lectures': initial_lectures,
                            'legend': map(lambda x: x[0], courses),
                            'semester': semester,
                            'slug': slug,
                            'table': table,
                        }, RequestContext(request))

def select_groups(request, year, type, slug):
    type = dict(map(lambda x: (x[1],x[0]), Semester.TYPES))[type.lower()]
    semester = Semester.objects.get(year=year, type=type)

    if request.method == 'POST':
        for c in Course.objects.filter(userset__slug=slug).distinct().order_by('id'):
            group_form = GroupForm(Group.objects.filter(lecture__course=c).distinct(), request.POST, prefix=c.id)

            if group_form.is_valid():
                set = UserSet.objects.get(course=c, slug=slug, semester=semester)
                set.groups = group_form.cleaned_data['groups']

    return HttpResponseRedirect(reverse('schedule-advanced', args=[semester.year,semester.get_type_display(),slug]))

def select_course(request, year, type, slug):
    highlight = []
    type = dict(map(lambda x: (x[1],x[0]), Semester.TYPES))[type.lower()]
    semester = Semester.objects.get(year=year, type=type)

    if request.method == 'POST' and 'course' in request.POST:
        if 'submit_add' in request.POST:
            lookup = request.POST['course'].split()

            for l in lookup:
                try:
                    course = Course.objects.get(name__iexact=l.strip())

                    highlight.append(str(course.id))

                    if not course.lecture_set.count():
                        scrape(request, l, no_auth=True)

                    userset, created = UserSet.objects.get_or_create(slug=slug, course=course, semester=semester)

                    for g in Group.objects.filter(lecture__course=course).distinct():
                        userset.groups.add(g)

                except Course.DoesNotExist:
                    # FIXME add user feedback
                    pass

            # FIXME semester
            url = reverse('schedule-advanced', args=[semester.year, semester.get_type_display(), slug])
            extra = ','.join(highlight)

            return HttpResponseRedirect('%s?highlight=%s' % (url, extra))

        elif 'submit_remove' in request.POST:
            courses = [c.strip() for c in request.POST.getlist('course') if c.strip()]
            sets = UserSet.objects.filter(slug__iexact=slug, course__id__in=courses)
            sets.delete()

    # FIXME semester
    return HttpResponseRedirect(reverse('schedule', args=[semester.year, semester.get_type_display(), slug]))

def select_lectures(request, slug):
    if request.method == 'POST':
        excludes = request.POST.getlist('exclude')

        for userset in UserSet.objects.filter(slug=slug):
            userset.exclude = userset.course.lecture_set.filter(id__in=excludes)

    return HttpResponseRedirect(reverse('schedule', args=[slug])+'?advanced=1')

# FIXME take in semester object
def scrape_list(request):
    '''Scrape the NTNU website to retrive all available courses'''
    if not request.user.is_authenticated():
        raise Http404

    abc = u'ABCDEFGHIJKLMNOPQRSTUVWXYÆØÅ'

    # FIMXE base on semester
    url = u'http://www.ntnu.no/studieinformasjon/timeplan/h08/?bokst=%s'

    courses = {}
    for letter in abc:
        html = ''.join(urlopen(url % urlquote(letter.encode('utf-8'))).readlines())
        soup = BeautifulSoup(html)

        for a in soup.findAll('a', href=re.compile('emnekode=[\w\d]+-1')):
            code = re.match('./\?emnekode=([\d\w]+)-1', a['href']).group(1)
            name = a.contents[0]

            if not name.startswith(code):
                courses[code] = name

    for name,full_name in sorted(courses.iteritems()):
        course, created = Course.objects.get_or_create(name=name.strip().upper())

        if not course.full_name:
            course.full_name = full_name
            course.save()

    return HttpResponse(str('\n'.join([str(c) for c in courses.items()])), mimetype='text/plain')

def scrape_exam(request, no_auth=False):
    # FIXME get into working shape
    if not request.user.is_authenticated() and not no_auth:
        raise Http404

    url = 'http://www.ntnu.no/eksamen/plan/08s/'

    html = ''.join(urlopen(url).readlines())
    soup = BeautifulSoup(html)

    main = soup.findAll('div', 'hovedramme')[0]

    results = []
    for tr in main.findAll('tr')[4:]:
        results.append({})

        for i,td in enumerate(tr.findAll('td')):
            if i == 0:
                results[-1]['course'] = td.contents
            elif i == 2:
                results[-1]['type'] = td.contents
            elif i == 3:
                results[-1]['time'] = td.findAll(text=lambda text: isinstance(text, NavigableString))
            elif i == 4:
                results[-1]['duration'] = td.contents
            elif i == 5:
                results[-1]['comment'] = td.contents

    for r in results:
        course, created = Course.objects.get_or_create(name=r['course'][0])

        try:

            if r['duration']:
                duration = r['duration'][0]
            else:
                duration = None

            if r['comment']:
                comment = r['comment'][0]
            else:
                comment = ''

            if ':' in r['time'][0]:
                date,time = r['time'][0].split()
                date = date.split('.')
                time = time.split(':')

                time = datetime(int(date[2]), int(date[1]), int(date[0]), int(time[0]), int(time[1]))
            else:
                time = r['time'][0].split('.')
                time = datetime(int(date[2]), int(date[1]), int(date[0]), int(time[0]))

            # FIXME handle multiple exams
            if r['type']:
                exam = Exam(course=course, type=r['type'].pop(), time=time, comment=comment, duration=duration)
                exam.save()
        except:
            pass

    return HttpResponse(str('\n'.join([str(r) for r in results])), mimetype='text/plain')

# FIXME take semester as parameter
def scrape(request, course, no_auth=False):
    '''Retrive all lectures for a given course'''
    if not no_auth and not request.user.is_authenticated():
        raise Http404

    # FIXME based on semester
    url = 'http://www.ntnu.no/studieinformasjon/timeplan/h08/?emnekode=%s-1' % course.upper().strip()

    html = ''.join(urlopen(url).readlines())
    soup = BeautifulSoup(html)
    main = soup.findAll('div', 'hovedramme')[0]
    table = main.findAll('table')[1]

    results = []

    text_only = lambda text: isinstance(text, NavigableString)

    title = table.findAll('h2')[0].contents[0].split('-')[2].strip()

    type = None
    for tr in table.findAll('tr')[2:-1]:
        time, weeks, room, lecturer, groups  = [], [], [], [], []
        lecture = True

        for i,td in enumerate(tr.findAll('td')):
            # Loop over our td's basing our action on the td's index in the tr
            # element.
            if i == 0:
                if td.get('colspan') == '4':
                    type = td.findAll(text=text_only)
                    lecture = False
                    break
                else:
                    for t in td.findAll('b')[0].findAll(text=text_only):
                        day, period = t.split(' ', 1)
                        start, end = [x.strip() for x in period.split('-')]
                        time.append([day,start,end])

                    for week in td.findAll('span')[0].contents[0].split()[1:]:
                        if '-' in week:
                            x,y = week.split('-')
                            weeks.extend(range(int(x),int(y)))
                        else:
                            weeks.append(int(week.replace(',', '')))
            elif i == 1:
                [room.extend(a.findAll(text=text_only)) for a in td.findAll('a')]
            elif i == 2:
                lecturer = [l.replace('&nbsp;', '') for l in td.findAll(text=text_only)]
            elif i == 3:
                groups = [p for p in td.findAll(text=text_only) if p.replace('&nbsp;','').strip()]

        if lecture:
            results.append({
                'type': type,
                'time': time,
                'weeks': weeks,
                'room': room,
                'lecturer': lecturer,
                'groups': groups,
                'title': title,
            })

    semester = Semester.objects.all()[0]
    course, created = Course.objects.get_or_create(name=course.upper())

    for r in results:
        if not course.full_name:
            course.full_name = r['title']
            course.save()
        room, created = Room.objects.get_or_create(name=r['room'][0])
        type, created = Type.objects.get_or_create(name=r['type'][0])

        day = ['Mandag', 'Onsdag', 'Tirsdag', 'Torsdag', 'Fredag'].index(r['time'][0][0])

        # We choose to be slightly naive and only care about which hour
        # something starts.
        start = int(r['time'][0][1].split(':')[0])
        end = int(r['time'][0][2].split(':')[0])

        start = dict(map(lambda x: (int(x[1].split(':')[0]),x[0]), Lecture.START))[start]
        end = dict(map(lambda x: (int(x[1].split(':')[0]),x[0]), Lecture.END))[end]

        lecture, created = Lecture.objects.get_or_create(
            course=course,
            day=day,
            semester=semester,
            start_time=start,
            end_time=end,
        )
        if r['groups']:
            for g in r['groups']:
                group, created = Group.objects.get_or_create(name=g)
                lecture.groups.add(group)
        else:
            group, created = Group.objects.get_or_create(name=Group.DEFAULT)

        for w in  r['weeks']:
            week, created = Week.objects.get_or_create(number=w)
            lecture.weeks.add(w)

        for l in r['lecturer']:
            if l.strip():
                lecturer, created = Lecturer.objects.get_or_create(name=l)
                lecture.lecturers.add(lecturer)

        lecture.room = room
        lecture.type = type
        lecture.save()

    return HttpResponse(str('\n'.join([str(r) for r in results])), mimetype='text/plain')
