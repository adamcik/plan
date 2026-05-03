# This file is part of the plan timetable generator, see LICENSE for details.

import datetime
import gzip
import math
import socket
import zoneinfo

import brotli
import vobject
from dateutil import rrule

from django import http, template, urls
from django.conf import settings
from django.core.cache import caches
from django.shortcuts import reverse
from django.utils import cache as cache_utils
from django.utils import http as http_utils
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


def _legacy_cache_key(request, schedule) -> str:
    return ":".join(
        str(p)
        for p in (
            "resp",
            request.resolver_match.url_name,
            request.path_info,
            schedule.last_modified,
        )
    )


def _response_cache_key(request, schedule, encoding: str) -> str:
    return ":".join(
        str(p)
        for p in (
            "resp",
            "v2",
            request.resolver_match.url_name,
            request.path_info,
            schedule.last_modified,
            encoding,
        )
    )


def _requested_encoding(request) -> str:
    accepts = utils.parse_accepts(request)
    if "br" in accepts:
        return "br"
    elif "gzip" in accepts:
        return "gzip"
    else:
        return "identity"


def _legacy_upgrade_response(response, encoding: str):
    current_encoding = response.headers.get("Content-Encoding")
    if encoding == "br" and current_encoding == "br":
        return response
    if encoding == "gzip" and current_encoding == "gzip":
        return response
    if encoding == "identity" and current_encoding is None:
        return response

    if current_encoding == "br":
        content = brotli.decompress(response.content)
    elif current_encoding == "gzip":
        content = gzip.decompress(response.content)
    else:
        content = response.content

    if encoding == "br":
        compressed = brotli.compress(content, brotli.MODE_TEXT)
        if len(compressed) < len(content):
            result = http.HttpResponse(
                compressed,
                status=response.status_code,
                headers=response.headers,
            )
            result["Content-Encoding"] = "br"
            result["Content-Length"] = str(len(compressed))
            cache_utils.patch_vary_headers(result, ("Accept-Encoding",))
            return result

    if encoding == "gzip":
        compressed = gzip.compress(content, compresslevel=6, mtime=0)
        if len(compressed) < len(content):
            result = http.HttpResponse(
                compressed,
                status=response.status_code,
                headers=response.headers,
            )
            result["Content-Encoding"] = "gzip"
            result["Content-Length"] = str(len(compressed))
            cache_utils.patch_vary_headers(result, ("Accept-Encoding",))
            return result

    result = http.HttpResponse(
        content,
        status=response.status_code,
        headers=response.headers,
    )
    if "Content-Encoding" in result:
        del result["Content-Encoding"]
    result["Content-Length"] = str(len(content))
    cache_utils.patch_vary_headers(result, ("Accept-Encoding",))
    return result


def ical(request, schedule, ical_type=None):
    resources = [_("lectures"), _("exams")]
    if ical_type and ical_type not in resources:
        return http.HttpResponse(status=400)
    elif ical_type:
        resources = [ical_type]

    if schedule.student is None:
        return http.HttpResponseNotFound()

    # TODO: Turn last modified into middleware?
    headers = {"X-Robots-Tag": "noindex, nofollow"}
    if schedule.last_modified is not None:
        headers["Last-Modified"] = http_utils.http_date(schedule.last_modified)

    if schedule.semester.stale:
        cache_timeout = datetime.timedelta(days=90)
    else:
        cache_timeout = datetime.timedelta(hours=6)

    if settings.TIMETABLE_ICAL_CACHE_DURATION is not None:
        internal_cache_timeout = (
            None
            if schedule.semester.stale
            else settings.TIMETABLE_ICAL_CACHE_DURATION.total_seconds()
        )
    else:
        internal_cache_timeout = None

    headers.update(utils.cache_headers(cache_timeout, jitter=0.1))

    response = utils.check_modified_since(
        request,
        schedule.last_modified,
        headers,
    )
    if response:
        return response

    # TODO: Turn caching into middleware
    bypass_cache = utils.should_bypass_cache(request)
    encoding = _requested_encoding(request)
    key = _response_cache_key(request, schedule, encoding)
    legacy_key = _legacy_cache_key(request, schedule)

    response = caches["ical"].get(key)
    if not bypass_cache and response:
        response["X-Cache"] = f"hit; key={key}"
        return response

    legacy_response = caches["ical"].get(legacy_key)
    if not bypass_cache and legacy_response:
        response = _legacy_upgrade_response(legacy_response, encoding)
        response["X-Cache"] = f"hit; legacy=1; key={legacy_key}; upgraded={key}"

        if settings.TIMETABLE_ICAL_CACHE_DURATION is not None:
            caches["ical"].set(
                key,
                response,
                timeout=internal_cache_timeout,
            )

        return response

    filename = utils.ical_filename(
        schedule.semester.year,
        schedule.semester.type,
        schedule.student.slug,
        resources,
    )

    headers["Filename"] = filename  # IE needs this
    headers["Content-Disposition"] = "attachment; filename=%s" % filename

    title = urls.reverse("schedule", args=[schedule])
    hostname = settings.TIMETABLE_HOSTNAME or request.headers.get(
        "Host", socket.getfqdn()
    )

    cal = vobject.iCalendar()
    cal.add("method").value = "PUBLISH"  # IE/Outlook needs this

    # TODO(adamcik): use same logic as in common.templatetags.title
    if schedule.student.slug.lower().endswith("s"):
        description = _("%(slug)s' %(semester)s %(year)s schedule for %(resources)s")
    else:
        description = _("%(slug)s's %(semester)s %(year)s schedule for %(resources)s")

    cal.add("X-WR-CALNAME").value = title.strip("/")
    cal.add("X-WR-CALDESC").value = description % {
        "slug": schedule.student.slug,
        "semester": schedule.semester.get_type_display(),
        "year": schedule.semester.year,
        "resources": ", ".join(resources),
    }

    if schedule.last_modified is not None:
        dtstamp = datetime.datetime.fromtimestamp(schedule.last_modified, tz=UTC)
    else:
        dtstamp = datetime.datetime.now(tz=UTC)

    if _("lectures") in resources:
        lectures = Lecture.objects.get_lectures(
            schedule.semester.id,
            schedule.student.id,
        )
        add_lectutures(
            lectures,
            schedule.semester.year,
            cal,
            request,
            hostname,
            dtstamp,
        )

    if _("exams") in resources:
        exams = Exam.objects.get_exams(
            schedule.semester.year,
            schedule.semester.type,
            schedule.student.slug,
        )
        add_exams(exams, cal, hostname, dtstamp)

    response = http.HttpResponse(
        cal.serialize(),
        content_type="text/calendar; charset=utf-8",
        headers=headers,
    )

    # NOTE: Most consumers will use compressed response, so we make a point of
    # compressing with the best possible compression that the current client
    # supports before putting things in the cache. We have compatibility
    # middleware that will decompress if needed.

    if settings.TIMETABLE_ICAL_CACHE_DURATION is not None:
        response["X-Cache"] = f"{'miss' if not bypass_cache else 'bypass'}; key={key}"
        response = utils.compress_response(request, response)
        caches["ical"].set(
            key,
            response,
            timeout=internal_cache_timeout,
        )
    else:
        response["X-Cache"] = f"disabled; key={key}"

    # TODO(adamcik): Rate limit remote hosts?
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


def add_lectutures(lectures, year, cal, request, hostname, dtstamp):
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
            vevent.add("dtstamp").value = dtstamp

            vevent.add("uid").value = "lecture-%d-%s@%s" % (
                l.id,
                d.strftime("%Y%m%d"),
                hostname,
            )

            if l.type and l.type.optional:
                vevent.add("transp").value = "TRANSPARENT"


def add_exams(exams, cal, hostname, dtstamp):
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
        vevent.add("dtstamp").value = dtstamp

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
