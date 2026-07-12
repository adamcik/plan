# This file is part of the plan timetable generator, see LICENSE for details.

import datetime
import gzip
import logging
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
logger = logging.getLogger(__name__)

TZ = zoneinfo.ZoneInfo(settings.TIME_ZONE)
UTC = zoneinfo.ZoneInfo("UTC")


def _to_utc(dt: datetime.datetime) -> datetime.datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=TZ).astimezone(UTC)
    return dt.astimezone(UTC)


def _cache_route_name(request) -> str:
    return str(request.resolver_match.url_name)


def _legacy_route_names(request) -> list[str]:
    route_name = _cache_route_name(request)
    names = [route_name]
    if route_name == "schedule-ical-type":
        names.append("schedule-ical-type-fallback")
    return names


def _legacy_paths(request) -> list[str]:
    path = request.path_info
    normalized = path.rstrip("/") or "/"
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


def _legacy_cache_keys(request, snapshot) -> list[str]:
    keys = []
    seen = set()
    encodings = ("identity", "gzip", "br")

    def _append(key: str):
        if key in seen:
            return
        seen.add(key)
        keys.append(key)

    for route_name in _legacy_route_names(request):
        for path in _legacy_paths(request):
            for encoding in encodings:
                _append(_legacy_v2_cache_key(path, route_name, snapshot, encoding))
            _append(_legacy_cache_key(path, route_name, snapshot))

        normalized_path = request.path_info.rstrip("/") or "/"
        for encoding in encodings:
            _append(
                utils.response_cache_key(
                    route_name,
                    snapshot.freshness_key(),
                    normalized_path,
                    encoding,
                )
            )
    return keys


def _legacy_upgrade_response(response):
    current_encoding = response.headers.get("Content-Encoding")

    if current_encoding == "br":
        content = brotli.decompress(response.content)
    elif current_encoding == "gzip":
        content = gzip.decompress(response.content)
    else:
        content = response.content

    result = http.HttpResponse(
        content,
        status=response.status_code,
        headers=response.headers,
    )
    if "Content-Encoding" in result:
        del result["Content-Encoding"]
    if "Vary" in result:
        del result["Vary"]
    result["Content-Length"] = str(len(content))
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

    internal_cache_timeout = settings.TIMETABLE_ICAL_CACHE_DURATION.total_seconds()
    if internal_cache_timeout <= 0:
        internal_cache_timeout = None

    bypass_cache = utils.should_bypass_cache(request)
    route = str(request.resolver_match.url_name)
    path = request.path_info
    cache_key = utils.response_cache_key(route, snapshot.freshness_key(), path)
    headers = utils.build_validator_headers(
        cache_key=cache_key,
        last_modified=snapshot.last_modified,
        extra_headers={"X-Robots-Tag": "noindex, nofollow"},
    )
    response = utils.check_not_modified(request, snapshot.last_modified, headers)
    if response:
        # This may return 304 before internal cache lookup/bypass.
        # `no-cache` requests still permit conditional 304 responses.
        return response

    response = utils.lookup_cached_response(
        cache_alias="disk",
        cache_key=cache_key,
        headers=headers,
        bypass=bypass_cache,
    )
    if response:
        return response

    if not bypass_cache:
        legacy_keys = _legacy_cache_keys(request, snapshot)
        legacy_cached = caches["ical"].get_many(legacy_keys)
        for candidate_key in legacy_keys:
            candidate_response = legacy_cached.get(candidate_key)
            if candidate_response is None:
                continue

            response = _legacy_upgrade_response(candidate_response)
            utils.apply_response_headers(response, headers)
            upgraded_header = f"hit; key={candidate_key}; upgraded={cache_key}"
            response["X-Cache"] = upgraded_header

            if internal_cache_timeout is not None:
                try:
                    stored = caches["disk"].set(
                        cache_key,
                        response,
                        timeout=internal_cache_timeout,
                    )
                    if stored is False:
                        raise RuntimeError("disk cache rejected response")
                except Exception:
                    logger.exception("Failed to promote iCal legacy cache response")
                response["X-Cache"] = upgraded_header

            caches["ical"].delete(candidate_key)

            return response

    filename = utils.ical_filename(snapshot, resources)

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
        lectures = Lecture.objects.get_lectures_data(
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
    )
    utils.apply_response_headers(response, headers)
    response["Filename"] = filename  # IE needs this
    response["Content-Disposition"] = "attachment; filename=%s" % filename

    # TODO(adamcik): Rate limit remote hosts?
    return utils.store_cached_response(
        cache_alias="disk",
        cache_key=cache_key,
        response=response,
        timeout=internal_cache_timeout,
        bypass=bypass_cache,
        queued=True,
    )


# TODO: Consider adding redirect/url-shortner for rooms?
DESCRIPTION_TEXT = template.Template(
    """
{{ lecture.course_name }} ({{ lecture.type_name|default:"" }})
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

    lecture_ids = [lecture.lecture_id for lecture in lectures]
    all_rooms = Lecture.get_related(Room, lecture_ids, fields=["id", "name", "url"])
    all_weeks = Lecture.get_related(
        Week,
        lecture_ids,
        fields=["number"],
        use_extra=False,
    )

    for l in lectures:
        if l.exclude:  # Skip excluded
            continue

        if l.lecture_id not in all_weeks:
            continue

        weeks = all_weeks[l.lecture_id]

        rrule_kwargs = {
            "byweekno": weeks,
            "count": len(weeks),
            "byweekday": l.day,
            "dtstart": datetime.datetime(int(year), 1, 1),
        }

        summary = l.alias or l.course_code
        if l.title:
            summary += "\n" + l.title

        rooms = []
        for r in all_rooms.get(l.lecture_id, []):
            if r["url"]:
                tmp = reverse("redirect_room", args=(r["id"],))
                r["url"] = request.build_absolute_uri(tmp)
            rooms.append(r)

        context = template.Context(
            {"lecture": l, "rooms": all_rooms.get(l.lecture_id, [])}
        )
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
                l.lecture_id,
                d.strftime("%Y%m%d"),
                hostname,
            )

            if l.type_optional:
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
