# This file is part of the plan timetable generator, see LICENSE for details.

import datetime
import math
import socket
import zoneinfo

import vobject
from dateutil import rrule

from django import http, template, urls
from django.conf import settings
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

_ = translation.gettext

TZ = zoneinfo.ZoneInfo(settings.TIME_ZONE)
UTC = zoneinfo.ZoneInfo("UTC")


def _to_utc(dt: datetime.datetime) -> datetime.datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=TZ).astimezone(UTC)
    return dt.astimezone(UTC)


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
