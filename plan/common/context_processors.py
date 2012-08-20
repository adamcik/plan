# This file is part of the plan timetable generator, see LICENSE for details.

from django.conf import settings
from django.utils import translation

_ = translation.gettext_lazy

def processor(request):
    sitename = settings.TIMETABLE_HOSTNAME or request.META['HTTP_HOST']

    share_links = []
    for icon, name, link in settings.TIMETABLE_SHARE_LINKS:
        share_links.append((icon, name, link % {'url': sitename}))

    institution_links = []
    for name, url in settings.TIMETABLE_INSTITUTION_LINKS:
        institution_links.append((_(name), url))

    return {'ANALYTICS_CODE': settings.TIMETABLE_ANALYTICS_CODE,
            'INSTITUTION': settings.TIMETABLE_INSTITUTION,
            'INSTITUTION_LINKS': institution_links,
            'INSTITUTION_SITE': settings.TIMETABLE_INSTITUTION_SITE,
            'MIGRATE_COOKIES': settings.TIMETABLE_MIGRATE_COOKIES,
            'ADMINS': settings.ADMINS,
            'SHARE_LINKS': share_links,
            'SOURCE_URL': settings.TIMETABLE_SOURCE_URL,
            'SITENAME': sitename,
            'STRIP_COOKIES': settings.TIMETABLE_STRIP_COOKIES}

