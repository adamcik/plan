# This file is part of the plan timetable generator, see LICENSE for details.

import datetime
import math
import socket
import zoneinfo

from django.utils.http import http_date
import vobject
from dateutil import rrule
from django import http, template, urls
from django.conf import settings
from django.core.cache import caches
from django.shortcuts import reverse
from django.utils import translation

from plan.common import utils
from plan.common.models import (
    Exam,
    Lecture,
    Room,
    Week,
)

_ = translation.gettext

TZ = zoneinfo.ZoneInfo(settings.TIME_ZONE)
UTC = zoneinfo.ZoneInfo("UTC")


def _to_utc(dt: datetime.datetime) -> datetime.datetime:
    return dt.replace(tzinfo=TZ).astimezone(UTC)


def ical(request, year, semester_type, slug, ical_type=None):
    resources = [_("lectures"), _("exams")]
    if ical_type and ical_type not in resources:
        return http.HttpResponse(status=400)
    elif ical_type:
        resources = [ical_type]

    filename = utils.ical_filename(year, semester_type, slug, resources)
    semester, student, last_modified = utils.fetch_student_semester(
        year, semester_type, slug
    )

    if semester is None or student is None:
        return http.HttpResponseNotFound()

    not_modified = utils.check_modified_since(request, last_modified)
    if not_modified:
        not_modified.headers["X-Robots-Tag"] = "noindex, nofollow"
        return not_modified

    # TODO: Turn last modified + caching into middleware?

    bypass_cache = utils.bypass_cache(request)
    key = "-".join(
        str(p)
        for p in (
            request.resolver_match.url_name,
            last_modified,
            request.path,
        )
    )

    response = caches["ical"].get(key)
    if not bypass_cache and response:
        response["X-Cache"] = f"hit; key={key}"

        if settings.DEBUG and "html" in request.GET:
            return utils.debug_response(utils.decompress_response(response))
        elif not utils.accepts_gzip(request):
            return utils.decompress_response(response)
        return response

    title = urls.reverse("schedule", args=[year, semester_type, slug])
    hostname = settings.TIMETABLE_HOSTNAME or request.headers.get(
        "Host", socket.getfqdn()
    )

    cal = vobject.iCalendar()
    cal.add("method").value = "PUBLISH"  # IE/Outlook needs this

    # TODO(adamcik): use same logic as in common.templatetags.title
    if slug.lower().endswith("s"):
        description = _("%(slug)s' %(semester)s %(year)s schedule for %(resources)s")
    else:
        description = _("%(slug)s's %(semester)s %(year)s schedule for %(resources)s")

    cal.add("X-WR-CALNAME").value = title.strip("/")
    cal.add("X-WR-CALDESC").value = description % {
        "slug": slug,
        "semester": semester.get_type_display(),
        "year": semester.year,
        "resources": ", ".join(resources),
    }

    if _("lectures") in resources:
        lectures = Lecture.objects.get_lectures(semester.id, student.id)
        add_lectutures(lectures, semester.year, cal, request, hostname)

    if _("exams") in resources:
        exams = Exam.objects.get_exams(year, semester.type, slug)
        add_exams(exams, cal, hostname)

    if semester.stale:
        cache_timeout = datetime.timedelta(days=90)
    else:
        cache_timeout = datetime.timedelta(hours=6)

    response = http.HttpResponse(
        cal.serialize(),
        content_type="text/calendar; charset=utf-8",
        headers=utils.cache_headers(cache_timeout, jitter=0.1),
    )

    if last_modified > 0:
        response["Last-Modified"] = http_date(last_modified)

    response["Filename"] = filename  # IE needs this
    response["Content-Disposition"] = "attachment; filename=%s" % filename
    response["X-Robots-Tag"] = "noindex, nofollow"

    # NOTE: Most consumers will use compressed response, so do this once before
    # caching to save resources. The alternative is to vary the cache key based
    # on gzip, or just not bother with the complexity of compressing.

    if settings.TIMETABLE_ICAL_CACHE_DURATION:
        response["X-Cache"] = f"{'miss' if not bypass_cache else 'bypass'}; key={key}"
        compressed_response = utils.compress_response(response)
        caches["ical"].set(
            key,
            compressed_response,
            timeout=settings.TIMETABLE_ICAL_CACHE_DURATION.total_seconds(),
        )
    else:
        response["X-Cache"] = f"disabled; key={key}"
        compressed_response = None

    # TODO(adamcik): Rate limit remote hosts?

    if settings.DEBUG and "html" in request.GET:
        return utils.debug_response(response)
    elif utils.accepts_gzip(request) and compressed_response:
        return compressed_response
    else:
        return response


# TODO: Consider adding redirect/url-shortner for rooms?
DESCRIPTION_TEXT = template.Template(
    """
{{ lecture.course.name }} ({{ lecture.type|default:"" }})
{% if lecture.stream %}
Stream: {{ lecture.stream }}
{% endif %}
{{ lecture.title|default:"" }}{% if lecture.summary and lecture.title %} - {% endif %}{{ lecture.summary|default:"" }}
{% for room in rooms %}
 - {{ room.name }}{% if room.url %}, {{ room.url }}{% endif %}{% endfor %}
""".strip()
)


def add_lectutures(lectures, year, cal, request, hostname):
    """Adds lectures to cal object for current semester"""

    all_rooms = Lecture.get_related(Room, lectures, fields=["id", "name", "url"])
    all_weeks = Lecture.get_related(Week, lectures, fields=["number"], use_extra=False)

    for l in lectures:
        if l.exclude:  # Skip excluded
            continue

        if l.id not in all_weeks:
            continue

        weeks = all_weeks[l.id]

        rrule_kwargs = {
            "byweekno": weeks,
            "count": len(weeks),
            "byweekday": l.day,
            "dtstart": datetime.datetime(int(year), 1, 1),
        }

        summary = l.alias or l.course.code
        if l.title:
            summary += "\n" + l.title

        rooms = []
        for r in all_rooms.get(l.id, []):
            if r["url"]:
                tmp = reverse("redirect_room", args=(r["id"],))
                r["url"] = request.build_absolute_uri(tmp)
            rooms.append(r)

        context = template.Context({"lecture": l, "rooms": all_rooms.get(l.id, [])})
        desc = DESCRIPTION_TEXT.render(context)

        for d in rrule.rrule(rrule.WEEKLY, **rrule_kwargs):
            vevent = cal.add("vevent")
            vevent.add("summary").value = summary
            vevent.add("location").value = ", ".join(r["name"] for r in rooms)
            vevent.add("description").value = desc

            vevent.add("dtstart").value = _to_utc(
                d.replace(hour=l.start.hour, minute=l.start.minute)
            )
            vevent.add("dtend").value = _to_utc(
                d.replace(hour=l.end.hour, minute=l.end.minute)
            )
            vevent.add("dtstamp").value = datetime.datetime.utcnow()

            vevent.add("uid").value = "lecture-%d-%s@%s" % (
                l.id,
                d.strftime("%Y%m%d"),
                hostname,
            )

            if l.type and l.type.optional:
                vevent.add("transp").value = "TRANSPARENT"


def add_exams(exams, cal, hostname):
    for e in exams:
        vevent = cal.add("vevent")

        if e.type and e.type.name:
            summary = f"{e.type.name} - {e.alias or e.course.name}"
            desc = "{} ({}) - {} ({})".format(
                e.type.name, e.type.code, e.course.name, e.course.code
            )
        elif e.type:
            summary = _("Exam") + f" ({e.type}) - {e.alias or e.course.code}"
            desc = _("Exam") + " ({}) - {} ({})".format(
                e.type.code, e.course.name, e.course.code
            )
        else:
            summary = _("Exam") + " %s" % (e.alias or e.course.code)
            desc = _("Exam") + f" {e.course.name} ({e.course.code})"

        vevent.add("summary").value = summary
        vevent.add("description").value = desc
        vevent.add("dtstamp").value = datetime.datetime.utcnow()

        vevent.add("uid").value = "exam-%d@%s" % (e.id, hostname)

        if e.handout_date:
            if e.handout_time:
                vevent.add("dtstart").value = _to_utc(
                    datetime.datetime.combine(e.handout_date, e.handout_time)
                )
            else:
                vevent.add("dtstart").value = e.handout_date

            if e.exam_time:
                vevent.add("dtend").value = _to_utc(
                    datetime.datetime.combine(e.exam_date, e.exam_time)
                )
            else:
                vevent.add("dtend").value = e.exam_date
        else:
            if e.exam_time:
                start = _to_utc(datetime.datetime.combine(e.exam_date, e.exam_time))
            else:
                start = e.exam_date

            vevent.add("dtstart").value = start

            if e.duration and e.exam_time:
                hours = int(math.floor(e.duration))
                minutes = int((e.duration % 1) * 60)
                vevent.add("dtend").value = start + datetime.timedelta(
                    hours=hours, minutes=minutes
                )
            else:
                vevent.add("dtend").value = start
