# This file is part of the plan timetable generator, see LICENSE for details.

from django.conf import settings


def source_url(request):
    return {'SOURCE_URL': settings.SOURCE_URL}

