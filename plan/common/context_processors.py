# This file is part of the plan timetable generator, see LICENSE for details.

from django.conf import settings
from django.utils import translation

_ = translation.gettext_lazy

def processor(request):
    return {'ANALYTICS_CODE': settings.TIMETABLE_ANALYTICS_CODE,
            'INSTITUTION': settings.TIMETABLE_INSTITUTION,
            'INSTITUTION_LINKS': [(_(name), url) for name, url in
                                  settings.TIMETABLE_INSTITUTION_LINKS],
            'INSTITUTION_SITE': settings.TIMETABLE_INSTITUTION_SITE,
            'MIGRATE_COOKIES': settings.TIMETABLE_MIGRATE_COOKIES,
            'ADMINS': settings.ADMINS,
            'SOURCE_URL': settings.TIMETABLE_SOURCE_URL,
            'STRIP_COOKIES': settings.TIMETABLE_STRIP_COOKIES}

