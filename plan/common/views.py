from datetime import datetime
from urllib import urlopen
from BeautifulSoup import BeautifulSoup, NavigableString

from django.shortcuts import get_object_or_404, render_to_response
from django.template.context import RequestContext
from django.http import HttpResponseRedirect, HttpResponse

from plan.common.models import *
from plan.common.forms import *

MAX_COLORS = 8

def schedule(request, slug, year=None, semester=None):
    # Data structure that stores what will become the html table
    table = [[[{}] for a in Lecture.DAYS] for b in Lecture.START]
    # Extra info used to get the table right
    lectures = []

    # Color mapping for the courses
    color_map = {}
    color_index = 0

    # Default to current year
    if not year:
        year = datetime.now().year

    # Default to current semester
    if not semester:
        if datetime.now().month <= 6:
            semester = Semester.SPRING
        else:
            semester = Semester.FALL
        semester_display = dict(Semester.TYPES)[semester]
    else:
       semester_display = semester
       semester = dict(map(lambda x: (x[1],x[0]), SEMESTER.TYPES))[semester.lower()]

    # Get all lectures for userset during given period
    for i,lecture in enumerate(Lecture.objects.filter(course__userset__slug=slug, semester__year__exact=year, semester__type__exact=semester).order_by('course__id')):
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
            for j,time in enumerate(Lecture.START):
                table[j][lecture.day].append({})

        start = first
        remove = False

        # Set the css class for the color map
        if lecture.course_id not in color_map:
            color_index = (color_index + 1) % MAX_COLORS
            color_map[lecture.course_id] = 'lecture%d' % color_index

        css = [color_map[lecture.course_id]]

        if rowspan == 1:
            css.append('single')

        while start <= end:
            # Replace the cell we found with a hase containing info about our
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

    courses = []
    courses_intial = []
    legend = []

    for c in Course.objects.filter(userset__slug=slug, lecture__semester__year__exact=year, lecture__semester__type__exact=semester).distinct().order_by('id'):
        legend.append((c, color_map[c.id]))
        courses_intial.append(c.id)

        intial = {'groups': Group.objects.filter(userset__slug=slug).distinct()}
        group_form = GroupForm(Group.objects.filter(lecture__course=c).distinct(), initial=intial)

        courses.append([c, group_form])

    return render_to_response('common/schedule.html', {
                            'table': table,
                            'legend': legend,
                            'courses': courses,
                            'colspan': span,
                            'slug': slug,
                            'year': year,
                            'course_form': CourseForm(initial={'courses': courses_intial}),
                            'semester': semester_display,
                        }, RequestContext(request))

def scrape(request, course):
    url = 'http://www.ntnu.no/studieinformasjon/timeplan/h08/?emnekode=%s-1'

    html = ''.join(urlopen(url % course.upper()).readlines())
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
                'week': weeks,
                'room': room,
                'lecturer': lecturer,
                'groups': groups,
                'title': title,
            })

    semester = Semester.objects.all()[0]
    for r in results:
        c, created = Course.objects.get_or_create(name=course.upper())
        room, created = Room.objects.get_or_create(name=r['room'][0])
        type, created = Type.objects.get_or_create(name=r['type'][0])

        day = ['Mandag', 'Onsdag', 'Tirsdag', 'Torsdag', 'Fredag'].index(r['time'][0][0])

        start = r['time'][0][1]
        end = r['time'][0][2]

        if len(start) == 4:
            start = '0%s' % start
        if len(end) == 4:
            end = '0%s' % end

        start = dict(map(lambda x: (x[1],x[0]), Lecture.START))[start]
        end = dict(map(lambda x: (x[1],x[0]), Lecture.END))[end]

        lecture, created = Lecture.objects.get_or_create(
            course = c,
            day = day,
            semester = semester,
            start_time = start,
            end_time = end,
        )
        for g in r['groups']:
            group, created = Group.objects.get_or_create(name=g)
            lecture.groups.add(group)

        lecture.room = room
        lecture.type = type
        lecture.save()

    return HttpResponse(str('\n'.join([str(r) for r in results])), mimetype='text/plain')

