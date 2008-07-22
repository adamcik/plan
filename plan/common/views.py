from datetime import datetime

from django.shortcuts import get_object_or_404, render_to_response
from django.template.context import RequestContext

from plan.common.models import *

MAX_COLORS = 8

def list(request):
    pass

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
            semester = Lecture.SPRING
        else:
            semester = Lecture.FALL
    else:
       semester = dict(map(lambda x: (x[1],x[0]), Lecture.SEMESTER))[semester.lower()]

    # Get all lectures for userset during given period
    for i,lecture in enumerate(Lecture.objects.filter(course__userset__slug=slug, year=year, semester=semester)):
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

        while start <= end:
            # Replace the cell we found with a hase containing info about our
            # lecture
            table[start][lecture.day][row] = {
                'lecture': lecture,
                'rowspan': rowspan,
                'remove': remove,
                'class': color_map[lecture.course_id],
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
    for c in Course.objects.filter(userset__slug=slug, lecture__year__exact=year, lecture__semester__exact=semester):
        courses.append((c, color_map[c.id]))

    return render_to_response('common/schedule.html', {
                            'table': table,
                            'legend': courses,
                            'colspan': span
                        }, RequestContext(request))
