# This file is part of the plan timetable generator, see LICENSE for details.

import socket
import urllib.parse

from django import urls
from django.conf import settings
from django.utils import translation

_ = translation.gettext_lazy


def processor(request):
    sitename = settings.TIMETABLE_HOSTNAME or request.headers.get(
        "Host", socket.getfqdn()
    )
    scheme = "https://" if request.is_secure() else "http://"
    url = scheme + sitename + urls.reverse("frontpage")

    share_links = []
    for icon, name, link in settings.TIMETABLE_SHARE_LINKS:
        share_links.append((icon, name, link % {"url": url}))

    static_domain = urllib.parse.urlparse(settings.STATIC_URL).netloc.split(":")[0]
    if static_domain == sitename:
        static_domain = None

    return {
        "ANALYTICS_CODE": settings.TIMETABLE_ANALYTICS_CODE,
        "INSTITUTION": settings.TIMETABLE_INSTITUTION,
        "INSTITUTION_SITE": settings.TIMETABLE_INSTITUTION_SITE,
        "SHOW_SYLLABUS": settings.TIMETABLE_SHOW_SYLLABUS,
        "ADMINS": settings.ADMINS,
        "SHARE_LINKS": share_links,
        "SOURCE_URL": settings.TIMETABLE_SOURCE_URL,
        "STATIC_DOMAIN": static_domain,
        "SITENAME": sitename,
        "CSP_NONCE": getattr(request, "_csp_nonce", None),
    }
