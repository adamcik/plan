# This file is part of the plan timetable generator, see LICENSE for details.

from django.conf import settings


def source_url(request):
    return {'SOURCE_URL': settings.TIMETABLE_SOURCE_URL}


def analytics_code(request):
    return {'ANALYTICS_CODE': settings.TIMETABLE_ANALYTICS_CODE}
