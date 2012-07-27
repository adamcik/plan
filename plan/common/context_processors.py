# This file is part of the plan timetable generator, see LICENSE for details.

from django.conf import settings


def processor(request):
    return {'ANALYTICS_CODE': settings.TIMETABLE_ANALYTICS_CODE,
            'MIGRATE_COOKIES': settings.TIMETABLE_MIGRATE_COOKIES,
            'SOURCE_URL': settings.TIMETABLE_SOURCE_URL,
            'STRIP_COOKIES': settings.TIMETABLE_STRIP_COOKIES}

