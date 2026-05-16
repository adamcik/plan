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
from plan.common.snapshot import ScheduleSnapshotNotFound, get_schedule_snapshot
from plan.ical.queue import enqueue_cache_set

_ = translation.gettext

TZ = zoneinfo.ZoneInfo(settings.TIME_ZONE)
UTC = zoneinfo.ZoneInfo("UTC")


def _to_utc(dt: datetime.datetime) -> datetime.datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=TZ).astimezone(UTC)
    return dt.astimezone(UTC)


def _normalized_path(path: str) -> str:
    if path == "/":
        return path
    return path.rstrip("/")


def _cache_route_name(request) -> str:
    # Keep cache key stable across canonical `/ical/<type>/` and legacy
    # `/ical/<type>` fallback routes so both URL shapes share one entry.
    name = request.resolver_match.url_name
    if name == "schedule-ical-type-fallback":
        return "schedule-ical-type"
    return str(name)


def _legacy_route_names(request) -> list[str]:
    route_name = _cache_route_name(request)
    names = [route_name]
    if route_name == "schedule-ical-type":
        names.append("schedule-ical-type-fallback")
    return names


def _legacy_paths(request) -> list[str]:
    path = request.path_info
    normalized = _normalized_path(path)
    paths = [normalized]
    if path not in paths:
        paths.append(path)
    if normalized != "/":
        with_slash = f"{normalized}/"
        if with_slash not in paths:
            paths.append(with_slash)
    return paths


def _legacy_cache_key(path: str, route_name: str, schedule) -> str:
    return ":".join(
        str(p)
        for p in (
            "resp",
            route_name,
            path,
            schedule.last_modified,
        )
    )


def _legacy_v2_cache_key(path: str, route_name: str, schedule, encoding: str) -> str:
    return ":".join(
        str(p)
        for p in (
            "resp",
            "v2",
            route_name,
            path,
            schedule.last_modified,
            encoding,
        )
    )


def _legacy_cache_keys(request, schedule, encoding: str) -> list[str]:
    keys = []
    seen = set()

    def _append(key: str):
        if key in seen:
            return
        seen.add(key)
        keys.append(key)

    for route_name in _legacy_route_names(request):
        for path in _legacy_paths(request):
            _append(_legacy_v2_cache_key(path, route_name, schedule, encoding))
            _append(_legacy_cache_key(path, route_name, schedule))
    return keys


def _current_cache_key(request, schedule, encoding: str) -> str:
    return utils.response_cache_key(
        _cache_route_name(request),
        schedule.freshness_key(),
        _normalized_path(request.path_info),
        encoding,
    )


def _current_cache_keys(request, schedule, encoding: str) -> list[str]:
    keys = [_current_cache_key(request, schedule, encoding)]
    for fallback_encoding in _fallback_encodings(encoding):
        keys.append(_current_cache_key(request, schedule, fallback_encoding))
    return keys


def _requested_encoding(request) -> str:
    accepts = utils.parse_accepts(request)
    if "br" in accepts:
        return "br"
    elif "gzip" in accepts:
        return "gzip"
    else:
        return "identity"


def _fallback_encodings(encoding: str) -> list[str]:
    if encoding == "br":
        return ["gzip", "identity"]
    elif encoding == "gzip":
        return ["br", "identity"]
    else:
        return ["gzip", "br"]


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


def ical(request, semester, slug, ical_type=None):
    try:
        snapshot = get_schedule_snapshot(semester, slug)
    except ScheduleSnapshotNotFound:
        return http.HttpResponseNotFound()

    resources = [_("lectures"), _("exams")]
    if ical_type and ical_type not in resources:
        return http.HttpResponse(status=400)
    elif ical_type:
        resources = [ical_type]

    if snapshot.student is None:
        return http.HttpResponseNotFound()

    # TODO: Turn last modified into middleware?
    headers = {"X-Robots-Tag": "noindex, nofollow"}
    if snapshot.last_modified is not None:
        headers["Last-Modified"] = http_utils.http_date(snapshot.last_modified)

    if snapshot.semester.stale:
        cache_timeout = datetime.timedelta(days=90)
    else:
        cache_timeout = datetime.timedelta(hours=1)

    if settings.TIMETABLE_ICAL_CACHE_DURATION is not None:
        internal_cache_timeout = settings.TIMETABLE_ICAL_CACHE_DURATION.total_seconds()
    else:
        internal_cache_timeout = None

    headers.update(utils.cache_headers(cache_timeout, jitter=0.1))

    encoding = _requested_encoding(request)
    key = _current_cache_key(request, snapshot, encoding)
    headers["ETag"] = utils.etag_for_key(key)

    response = utils.check_not_modified(
        request,
        snapshot.last_modified,
        headers,
    )
    if response:
        # This may return 304 before internal cache lookup/bypass.
        # `no-cache` requests still permit conditional 304 responses.
        return response

    # TODO: Turn caching into middleware
    bypass_cache = utils.should_bypass_cache(request)

    if not bypass_cache:
        current_keys = _current_cache_keys(request, snapshot, encoding)
        legacy_keys = _legacy_cache_keys(request, snapshot, encoding)
        current_cached = caches["ical"].get_many(current_keys)
        for index, candidate_key in enumerate(current_keys):
            candidate_response = current_cached.get(candidate_key)
            if not candidate_response:
                continue

            response = _legacy_upgrade_response(candidate_response, encoding)
            response["ETag"] = headers["ETag"]
            if index == 0:
                response["X-Cache"] = f"hit; key={key}"
            else:
                response["X-Cache"] = f"hit; key={key}; fallback={candidate_key}"

            if settings.TIMETABLE_ICAL_CACHE_DURATION is not None:
                enqueue_cache_set(
                    key,
                    response,
                    timeout=internal_cache_timeout,
                )

            return response

        legacy_cached = caches["ical"].get_many(legacy_keys)
        for candidate_key in legacy_keys:
            candidate_response = legacy_cached.get(candidate_key)
            if not candidate_response:
                continue

            response = _legacy_upgrade_response(candidate_response, encoding)
            response["ETag"] = headers["ETag"]
            response["X-Cache"] = f"hit; key={candidate_key}; upgraded={key}"

            if settings.TIMETABLE_ICAL_CACHE_DURATION is not None:
                enqueue_cache_set(
                    key,
                    response,
                    timeout=internal_cache_timeout,
                )

            caches["ical"].delete(candidate_key)

            return response

    filename = utils.ical_filename(snapshot, resources)

    headers["Filename"] = filename  # IE needs this
    headers["Content-Disposition"] = "attachment; filename=%s" % filename

    title = urls.reverse("schedule", args=[snapshot.semester, snapshot.student.slug])
    hostname = settings.TIMETABLE_HOSTNAME or request.headers.get(
        "Host", socket.getfqdn()
    )

    cal = vobject.iCalendar()
    cal.add("method").value = "PUBLISH"  # IE/Outlook needs this

    # TODO(adamcik): use same logic as in common.templatetags.title
    if snapshot.student.slug.lower().endswith("s"):
        description = _("%(slug)s' %(semester)s %(year)s schedule for %(resources)s")
    else:
        description = _("%(slug)s's %(semester)s %(year)s schedule for %(resources)s")

    cal.add("X-WR-CALNAME").value = title.strip("/")
    cal.add("X-WR-CALDESC").value = description % {
        "slug": snapshot.student.slug,
        "semester": snapshot.semester.get_type_display(),
        "year": snapshot.semester.year,
        "resources": ", ".join(resources),
    }

    if snapshot.last_modified is not None:
        dtstamp = datetime.datetime.fromtimestamp(snapshot.last_modified, tz=UTC)
    else:
        dtstamp = datetime.datetime.now(tz=UTC)

    if _("lectures") in resources:
        lectures = Lecture.objects.get_lectures(
            snapshot.semester.id,
            snapshot.student.id,
        )
        add_lectutures(
            lectures,
            snapshot.semester.year,
            cal,
            request,
            hostname,
            dtstamp,
        )

    if _("exams") in resources:
        exams = Exam.objects.get_exams(
            snapshot.semester.year,
            snapshot.semester.type,
            snapshot.student.slug,
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
        enqueue_cache_set(
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
