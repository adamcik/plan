from django.shortcuts import get_object_or_404, render_to_response
from django.template.context import RequestContext

from plan.common.models import *

def test(request):
    table = [[[{}] for a in Lecture.DAYS] for b in Lecture.START]

    lectures = Lecture.objects.all()

    for i,lecture in enumerate(lectures):
        start = lecture.first_period - Lecture.START[0][0]
        end = lecture.last_period    - Lecture.END[0][0]
        rowspan = end - start

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
        while start <= end:
            table[start][lecture.day][row] = {
                'lecture': lecture,
                'rowspan': rowspan,
                'remove': remove,
            }
            remove = True
            start += 1


    return render_to_response('common/test.html', {'table': table, 'lectures': lectures}, RequestContext(request))
