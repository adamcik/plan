from django.shortcuts import get_object_or_404, render_to_response
from django.template.context import RequestContext

from plan.common.models import *

def test(request):
    table = [[{'lectures': []} for a in Lecture.DAYS] for b in Lecture.START]
    span = [1 for a in Lecture.DAYS]

    for l in Lecture.objects.all():
        start = l.first_period-Lecture.START[0][0]
        end = l.last_period-Lecture.START[0][0]

        while start < end:
            table[start][l.day]['lectures'].append(l)
            start += 1

    for x in range(len(Lecture.START)):
        for y in range(len(Lecture.DAYS)):
            if len(table[x][y]['lectures']) > span[y]:
                span[y] = len(table[x][y]['lectures'])

    for x in range(len(Lecture.START)):
        for y in range(len(Lecture.DAYS)):
            if len(table[x][y]['lectures']) > 1:
                table[x][y]['span'] = span[y] - len(table[x][y]['lectures']) or 1
            else:
                table[x][y]['span'] = span[y]

    return render_to_response('common/test.html', {'table': table, 'span': span}, RequestContext(request))
