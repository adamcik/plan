# This file is part of the plan timetable generator, see LICENSE for details.

import datetime
import math
import socket

import vobject
from dateutil import rrule, tz
from django import http, template, urls
from django.conf import settings
from django.core.cache import cache
from django.db.models import Max
from django.http.response import http_date
from django.shortcuts import reverse
from django.utils import translation
from django.utils.http import parse_http_date_safe

from plan.common import utils
from plan.common.models import Exam, Lecture, Room, Semester, Subscription, Week

_ = translation.gettext


# TODO: Put last modified ts a cache key, and delete that on all posts. I.e.
# the old way of doing it.
def ical(request, year, semester_type, slug, ical_type=None):
    resources = [_("lectures"), _("exams")]
    if ical_type and ical_type not in resources:
        raise ValueError("Invalid ical_type")
    elif ical_type:
        resources = [ical_type]

    try:
        filename = utils.ical_filename(year, semester_type, slug, resources)
    except ValueError:
        return http.HttpResponse(status=400)

    response = cache.get(filename)
    if response is not None:
        response["X-Cache"] = "hit"
        return response

    try:
        semester: Semester = Semester.objects.get(year=year, type=semester_type)
    except Semester.DoesNotExist:
        return http.HttpResponseNotFound()

    qs = Subscription.objects.filter(
        course__semester=semester,
        student__slug=slug,
    ).aggregate(
        subscription_added=Max("added"),
        subscription_last_modified=Max("last_modified"),
        courses_last_modified=Max("course__last_modified"),
        lectures_last_modified=Max("course__lecture__last_modified"),
        rooms_last_modified=Max("course__lecture__rooms__last_modified"),
        exams_last_modified=Max("course__exam__last_modified"),
    )
    # NOTE: last_modified == 0 implies the slug/subs don't exist.
    # We could bail here and return a 404, but instead we just give an empty ical.
    last_modified = max([0] + [int(agg.timestamp()) for agg in qs.values() if agg])

    if_modified_since = parse_http_date_safe(request.META.get("HTTP_IF_MODIFIED_SINCE"))

    if semester.stale:
        cache_timeout = datetime.timedelta(days=90)
    else:
        cache_timeout = datetime.timedelta(hours=6)

    headers = utils.cache_headers(cache_timeout, jitter=0.1)
    headers["X-Robots-Tag"] = "noindex, nofollow"

    if last_modified > 0:
        headers["Last-Modified"] = http_date(last_modified)

    if if_modified_since is not None and last_modified <= if_modified_since:
        return http.HttpResponseNotModified(headers=headers)

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
        lectures = Lecture.objects.get_lectures(year, semester.type, slug)
        add_lectutures(lectures, semester.year, cal, request, hostname)

    if _("exams") in resources:
        exams = Exam.objects.get_exams(year, semester.type, slug)
        add_exams(exams, cal, hostname)

    icalstream = cal.serialize()

    response = http.HttpResponse(
        icalstream, content_type="text/calendar", headers=headers
    )
    response["Content-Type"] = "text/calendar; charset=utf-8"
    response["Filename"] = filename  # IE needs this
    response["Content-Disposition"] = "attachment; filename=%s" % filename

    cache.set(filename, response, timeout=datetime.timedelta(days=7).total_seconds())
    response["X-Cache"] = "miss"

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
                tmp = reverse("room_redirect", args=(r["id"],))
                r["url"] = request.build_absolute_uri(tmp)
            rooms.append(r)

        context = template.Context({"lecture": l, "rooms": all_rooms.get(l.id, [])})
        desc = DESCRIPTION_TEXT.render(context)

        for d in rrule.rrule(rrule.WEEKLY, **rrule_kwargs):
            vevent = cal.add("vevent")
            vevent.add("summary").value = summary
            vevent.add("location").value = ", ".join(r["name"] for r in rooms)
            vevent.add("description").value = desc

            vevent.add("dtstart").value = d.replace(
                hour=l.start.hour, minute=l.start.minute, tzinfo=tz.tzlocal()
            )

            vevent.add("dtend").value = d.replace(
                hour=l.end.hour, minute=l.end.minute, tzinfo=tz.tzlocal()
            )

            vevent.add("dtstamp").value = datetime.datetime.now(tz.tzlocal())

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
        vevent.add("dtstamp").value = datetime.datetime.now(tz.tzlocal())

        vevent.add("uid").value = "exam-%d@%s" % (e.id, hostname)

        if e.handout_date:
            if e.handout_time:
                vevent.add("dtstart").value = datetime.datetime.combine(
                    e.handout_date, e.handout_time
                ).replace(tzinfo=tz.tzlocal())
            else:
                vevent.add("dtstart").value = e.handout_date

            if e.exam_time:
                vevent.add("dtend").value = datetime.datetime.combine(
                    e.exam_date, e.exam_time
                ).replace(tzinfo=tz.tzlocal())
            else:
                vevent.add("dtend").value = e.exam_date
        else:
            if e.exam_time:
                start = datetime.datetime.combine(e.exam_date, e.exam_time).replace(
                    tzinfo=tz.tzlocal()
                )
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
