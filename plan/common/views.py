from django.shortcuts import get_object_or_404, render_to_response
from django.template.context import RequestContext

from plan.common.models import *

MAX_COLORS = 8

def test(request):
    table = [[[{}] for a in Lecture.DAYS] for b in Lecture.START]
    lectures = []
    color_map = {}
    color_index = 0

    for i,lecture in enumerate(Lecture.objects.all()):
        start = lecture.first_period - Lecture.START[0][0]
        end = lecture.last_period    - Lecture.END[0][0]
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

        if lecture.course_id not in color_map:
            color_index = (color_index + 1) % MAX_COLORS
            color_map[lecture.course_id] = 'lecture%d' % color_index

        css = [color_map[lecture.course_id]]

        if row == 0:
            css.append('first')

        while start <= end:
            table[start][lecture.day][row] = {
                'lecture': lecture,
                'rowspan': rowspan,
                'remove': remove,
                'class': ' '.join(css),
            }

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
        i = lecture['i']
        j = lecture['j']
        m = lecture['m']
        height = lecture['height']

        expand_by = 1

        safe = True
        for l in xrange(m+1, len(table[i][j])):
            for k in xrange(i,i+height):
                print 'i %d, j %d, m %d' % (k,j,l)
                if table[k][j][l]:
                    safe = False
                    break
            if safe:
                expand_by += 1
            else:
                break

        table[i][j][m]['colspan'] = expand_by

        for l in xrange(m+1,m+expand_by):
            for k in xrange(i,i+height):
                table[k][j][l]['remove'] = True

    span = [1] * 5
    for i,cell in enumerate(table[0]):
        span[i] = len(cell)

    for t,start,end in map(lambda x,y: (x[0], x[1][1],y[1]), enumerate(Lecture.START), Lecture.END):
        table[t].insert(0, [{'time': '%s - %s' % (start, end), 'class': 'time'}])

    return render_to_response('common/test.html', {'table': table, 'colspan': span}, RequestContext(request))
