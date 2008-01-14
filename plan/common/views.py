from django.shortcuts import get_object_or_404, render_to_response
from django.template.context import RequestContext

from plan.common.models import *

def test(request):
    table = [[[] for a in Lecture.DAYS] for b in Lecture.START]

    for l in Lecture.objects.all():
        start = l.first_period-Lecture.START[0][0]
        end = l.last_period-Lecture.END[0][0]
        while start <= end:
            table[start][l.day].append(l)
            start += 1

    return render_to_response('common/test.html',
        {'table': table},
        RequestContext(request)
    )
