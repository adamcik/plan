# This file is part of the plan timetable generator, see LICENSE for details.

import datetime
import json
import urllib.parse

from django import http, shortcuts
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models import Model
from django.utils import html, text, translation
from django.utils.cache import patch_vary_headers
from django.utils.http import http_date

from plan.common import encoding, forms, timetable, utils
from plan.common.middleware import CspMiddleware
from plan.common.models import (
    Course,
    Exam,
    Group,
    Lecture,
    Location,
    Room,
    Semester,
    Student,
    Subscription,
    Week,
)
from plan.materialized.models import SubscriptionsCount

# FIXME split into frontpage/semester, course, schedule files
# FIXME Split views that do multiple form handling tasks into seperate views
# that call the top one.

# To allow for overriding of the codes idea of now() for tests
now = datetime.datetime.now
today = datetime.date.today

# Setup common alias for translation
_ = translation.gettext_lazy

# Start new week on saturdays
get_current_week = lambda: (now() + datetime.timedelta(days=2)).isocalendar()[1]


@utils.expires_in(datetime.timedelta(hours=1))
def frontpage(request):
    try:
        semester = Semester.objects.active()
    except Semester.DoesNotExist:
        raise http.Http404
    return shortcuts.redirect("semester", semester.year, semester.slug)


@utils.expires_in(datetime.timedelta(hours=1))
def shortcut(request, slug):
    """Redirect users to their timetable for the current semester"""
    try:
        semester = Semester.objects.active()
    except Semester.DoesNotExist:
        raise http.Http404
    return schedule_current(request, semester.year, semester.type, slug)


@utils.expires_in(datetime.timedelta(hours=1))
def redirect(request, type, id):
    try:
        if type == "room":
            url = Room.objects.get(id=id).url
        elif type == "syllabus":
            url = Course.objects.get(id=id).syllabus
        elif type == "course":
            url = Course.objects.get(id=id).url
        elif type == "stream":
            url = Lecture.objects.get(id=id).stream
        else:
            raise http.HttpResponseBadRequest()
    except Model.DoesNotExist:
        raise http.Http404

    if not url:
        raise http.Http404

    if settings.TIMETABLE_UTM_SOURCE:
        parts = list(urllib.parse.urlparse(url))
        query = dict(urllib.parse.parse_qsl(parts[4]))
        query.update({"utm_source": settings.TIMETABLE_UTM_SOURCE})
        parts[4] = urllib.parse.urlencode(query)
        url = urllib.parse.urlunparse(parts)

    return shortcuts.redirect(url)


@utils.expires_in(datetime.timedelta(hours=1))
def getting_started(request, year, semester_type):
    """Initial top level page that greets users"""
    try:
        semester = Semester.objects.get(year=year, type=semester_type)
    except Semester.DoesNotExist:
        raise http.Http404

    try:
        next_semester = next(Semester.objects)
    except Semester.DoesNotExist:
        next_semester = None

    if next_semester and next_semester == semester:
        next_semester = None

    # Redirect user to their timetable
    if request.method == "POST":
        schedule_form = forms.ScheduleForm(request.POST)

        if schedule_form.is_valid():
            slug = schedule_form.cleaned_data["slug"]
            # TODO(adamcik): what should we do if current is empty?
            return schedule_current(request, semester.year, semester.type, slug)
    else:
        schedule_form = forms.ScheduleForm()

    context = Course.get_stats(
        semester=semester,
        bypass_cache=utils.should_bypass_cache(request),
    )
    context.update(
        {
            "color_map": utils.ColorMap(hex=True),
            "current": semester,
            "next_semester": next_semester,
            "schedule_form": schedule_form,
        }
    )
    return shortcuts.render(request, "start.html", context)


def course_query(request, year, semester_type):
    try:
        limit = int(request.GET.get("limit", ""))
    except ValueError:
        limit = 100

    limit = min(limit, settings.TIMETABLE_AJAX_LIMIT)
    query = request.GET.get("q", "").strip()[:100]
    location = request.GET.get("l", "")
    course_list = []

    if query:
        course_list = Course.objects.search(
            year,
            semester_type,
            query,
            limit,
            location,
        )

    if request.headers.get("Accept") == "application/json":
        response = http.HttpResponse(content_type="application/json")
        json.dump(course_list, response)
    else:
        response = http.HttpResponse(content_type="text/plain; charset=utf-8")
        for code, name in course_list:
            code = html.escape(code)
            name = html.escape(text.Truncator(name).words(5, truncate="..."))
            response.write("{}|{}\n".format(code, name or ""))

    patch_vary_headers(response, ("Accept",))
    if settings.DEBUG and "html" in request.GET:
        return utils.debug_response(response)
    return response


def schedule_current(request, year, semester_type, slug):
    semester = Semester(year=year, type=semester_type)
    current_week = get_current_week()

    weeks = Week.objects.filter(
        lecture__course__subscription__student__slug=slug,
        lecture__course__semester__year__exact=semester.year,
        lecture__course__semester__type=semester.type,
    )
    weeks = weeks.distinct().values_list("number", flat=True)

    if current_week in weeks and semester.year == today().year:
        return shortcuts.redirect(
            "schedule-week", semester.year, semester.slug, slug, current_week
        )
    return shortcuts.redirect("schedule", semester.year, semester.slug, slug)


def schedule(request, year, semester_type, slug, advanced=False, week=None, all=False):
    """Page that handles showing schedules"""
    bypass_cache = utils.should_bypass_cache(request)

    current_week = get_current_week()
    if week:
        week = int(week)
        max_week = utils.max_number_of_weeks(year)
    if week is not None:
        if week <= 0 or week > max_week:
            raise http.Http404

    # Color mapping for the courses
    color_map = utils.ColorMap(hex=True)

    semester, student, last_modified = utils.fetch_student_semester(
        year, semester_type, slug
    )
    if not semester or not student:
        return http.HttpResponseNotFound()

    headers = {}
    if last_modified > 0:
        headers["Last-Modified"] = http_date(last_modified)

    response = utils.check_modified_since(request, last_modified, headers)
    if response:
        return response

    # TODO: Can we turn this into a middleware? That would allow us to cache
    # post minification and csp...
    key = "-".join(
        str(p)
        for p in (
            request.resolver_match.url_name,
            last_modified,
            request.path,
        )
    )
    response = cache.get(key)
    if not bypass_cache and response:
        response["X-Cache"] = f"hit; key={key}"

        if not utils.accepts_gzip(request):
            return utils.decompress_response(response)
        return response

    db_key = f"db:{year}-{semester_type}-{slug}-{last_modified}"
    result = cache.get(db_key)

    if result:
        lectures, courses, exams, lecturers, groups, rooms, schedule_weeks = result
    else:
        lectures = Lecture.objects.get_lectures(semester.id, student.id)
        courses = Course.objects.get_courses(year, semester.type, slug)

        # Most of these could be built into get_lectures with ARRAY_AGG..
        exams = {}
        for exam in Exam.objects.get_exams(year, semester.type, slug):
            exams.setdefault(exam.course_id, []).append(exam)

        # Use get_related to cut query counts
        lecturers = []  # Lecture.get_related(Lecturer, lectures)
        groups = Lecture.get_related(Group, lectures, fields=["code"])
        rooms = Lecture.get_related(Room, lectures, fields=["id", "name", "url"])

        schedule_weeks = set()
        for l in lectures:
            schedule_weeks.update(l.week_numbers)
        if schedule_weeks:
            schedule_weeks = list(range(min(schedule_weeks), max(schedule_weeks) + 1))

        # NOTE: This data can be used across pages, so cache it.

        # TODO: Should we consider a get_related for courses as well?
        # TODO: get_related duplicates data, perhaps the exams dict should just
        # be {lecture_id: exam_id} and then there is a {exam_id: exam} mapping?
        result = (lectures, courses, exams, lecturers, groups, rooms, schedule_weeks)
        cache.set(db_key, result, timeout=3600)

    common_key = "common"
    result = cache.get(common_key)
    if result:
        next_semester, next_message, locations = result
    else:
        locations = Location.objects.distinct()  # .filter(course__semester=semester)

        try:
            # TODO: try and turn this into a single query with annotate?
            next_semester = next(Semester.objects)
            # TODO: I think we only show the message if there is someone using it?
            next_message = (
                Subscription.objects.get_subscriptions(
                    next_semester.year, next_semester.type, slug
                ).count()
                == 0
            )
        except Semester.DoesNotExist:
            next_semester = None
            next_message = False

        result = (next_semester, next_message, locations)
        cache.set(common_key, result, timeout=8 * 3600)

    next_week = None
    prev_week = None

    if week and week + 1 in schedule_weeks:
        next_week = week + 1

    if week and week - 1 in schedule_weeks:
        prev_week = week - 1

    # Init colors in predictable maner
    for c in courses:
        color_map[c.id]

    # Create Timetable
    table = timetable.Timetable(lectures)

    if week:
        table.set_week(semester.year, week)

    if lectures:
        table.place_lectures(week)
        table.do_expansion()

    table.insert_times()
    table.add_markers()

    if advanced:
        # Set up and course name forms
        for course in courses:
            alias = course.alias or ""
            course.alias_form = forms.CourseAliasForm(
                initial={"alias": alias}, prefix=course.id
            )
            course.alias_form.fields["alias"].widget.attrs["title"] = _(
                "Display %(course)s as:"
            ) % {"course": course.code}

    week_is_current = semester.year == today().year and week == current_week

    # TODO: Natural sort course code? Why is this needed here?
    lectures.sort(
        key=lambda l: (
            l.course.code,
            min(l.week_numbers) if l.week_numbers else None,
        )
    )

    response = shortcuts.render(
        request,
        "schedule.html",
        {
            "advanced": advanced,
            "all": all,
            "color_map": color_map,
            "courses": courses,
            "current": (week == current_week),
            "current_week": current_week,
            "exams": exams,
            "next_message": next_message,
            "lectures": lectures,
            "semester": semester,
            "week_is_current": week_is_current,
            "next_semester": next_semester,
            "slug": slug,
            "timetable": table,
            "week": week,
            "next_week": next_week,
            "prev_week": prev_week,
            "rooms": rooms,
            "groups": groups,
            "lecturers": lecturers,
            "locations": locations,
            "weeks": schedule_weeks,
        },
    )
    for header, value in headers.items():
        response.headers[header] = value

    if settings.TIMETABLE_SCHEDULE_CACHE_DURATION:
        response["X-Cache"] = f"{'miss' if not bypass_cache else 'bypass'}; key={key}"
        CspMiddleware.store_nonce_in_header(request, response)

        # TODO: It would be nice to have the HTML minified and then stored
        # pre-compressed in the cache. Size difference is e.g. 6086 vs 77053.
        cache.set(
            key,
            response,
            timeout=settings.TIMETABLE_SCHEDULE_CACHE_DURATION.total_seconds(),
        )
    else:
        response["X-Cache"] = f"disabled; key={key}"

    return response


def select_groups(request, year, semester_type, slug):
    """Form handler for selecting groups to use in schedule"""
    courses = Course.objects.get_courses(year, semester_type, slug)
    course_groups = Course.get_groups(year, semester_type, [c.id for c in courses])

    if request.method == "POST":
        with transaction.atomic():
            for c in courses:
                try:
                    groups = course_groups[c.id]
                except KeyError:  # Skip courses without groups
                    continue

                group_form = forms.GroupForm(groups, request.POST, prefix=c.id)

                if group_form.is_valid():
                    subscription = Subscription.objects.get_subscriptions(
                        year, semester_type, slug
                    ).get(course=c)

                    subscription.groups.set(group_form.cleaned_data["groups"])
                    subscription.save()  # Update last modified.

            utils.clear_cache(year, semester_type, slug)

        return shortcuts.redirect(
            "schedule-advanced", year, Semester.localize(semester_type), slug
        )

    color_map = utils.ColorMap(hex=True)
    subscription_groups = Subscription.get_groups(year, semester_type, slug)
    all_subscripted_groups = set()

    for groups in subscription_groups.values():
        for group in groups:
            all_subscripted_groups.add(group)

    for c in courses:
        color_map[c.id]
        subscription_id = c.subscription_set.get(student__slug=slug).pk

        try:
            groups = course_groups[c.id]
        except KeyError:  # Skip courses without groups
            continue

        initial_groups = subscription_groups.get(
            subscription_id, all_subscripted_groups
        )

        c.group_form = forms.GroupForm(
            groups, prefix=c.id, initial={"groups": initial_groups}
        )

    return shortcuts.render(
        request,
        "select_groups.html",
        {
            "semester": Semester(year=year, type=semester_type),
            "slug": slug,
            "courses": courses,
            "color_map": color_map,
        },
    )


def select_course(request, year, semester_type, slug, add=False):
    """Handle selecting of courses from course list, change of names and
    removeall of courses"""

    # FIXME split ut three sub functions into seperate functions?

    try:
        semester = Semester.objects.get(year=year, type=semester_type)
    except Semester.DoesNotExist:
        return shortcuts.redirect(
            "schedule", year, Semester.localize(semester_type), slug
        )

    if request.method == "POST":
        if "submit_add" in request.POST or add:
            lookup = []

            for l in request.POST.getlist("course_add"):
                lookup.extend(l.replace(",", "").split())

            subscriptions = set(
                Subscription.objects.get_subscriptions(
                    year, semester_type, slug
                ).values_list("course__code", flat=True)
            )

            if not lookup:
                localized_semester = Semester.localize(semester_type)
                return shortcuts.redirect(
                    "schedule-advanced", year, localized_semester, slug
                )

            errors = []
            to_many_subscriptions = False

            student, created = Student.objects.get_or_create(slug=slug)

            for l in lookup:
                try:
                    if len(subscriptions) > settings.TIMETABLE_MAX_COURSES:
                        to_many_subscriptions = True
                        break

                    course = Course.objects.get(
                        code__iexact=l.strip(),
                        semester__year__exact=year,
                        semester__type__exact=semester_type,
                    )

                    Subscription.objects.get_or_create(
                        student=student,
                        course=course,
                    )
                    subscriptions.add(course.code)

                except Course.DoesNotExist:
                    errors.append(l)

            utils.clear_cache(year, semester_type, slug)

            if errors or to_many_subscriptions:
                return shortcuts.render(
                    request,
                    "error.html",
                    {
                        "courses": errors,
                        "max": settings.TIMETABLE_MAX_COURSES,
                        "slug": slug,
                        "year": year,
                        "type": semester_type,
                        "to_many_subscriptions": to_many_subscriptions,
                    },
                )

            return shortcuts.redirect(
                "change-groups", year, Semester.localize(semester_type), slug
            )

        elif "submit_remove" in request.POST:
            with transaction.atomic():
                courses = []
                for c in request.POST.getlist("course_remove"):
                    if c.strip():
                        courses.append(c.strip())

                Subscription.objects.get_subscriptions(
                    year, semester_type, slug
                ).filter(course__id__in=courses).delete()

                if Subscription.objects.filter(student__slug=slug).count() == 0:
                    Student.objects.filter(slug=slug).delete()

            utils.clear_cache(year, semester_type, slug)

        elif "submit_name" in request.POST:
            subscriptions = Subscription.objects.get_subscriptions(
                year, semester_type, slug
            )

            for u in subscriptions:
                form = forms.CourseAliasForm(request.POST, prefix=u.course_id)

                if form.is_valid():
                    alias = form.cleaned_data["alias"].strip()

                    if alias.upper() == u.course.code.upper() or alias == "":
                        # Leave as blank if we match the current course name
                        alias = ""

                    u.alias = alias
                    u.save()

            utils.clear_cache(year, semester_type, slug)

    return shortcuts.redirect(
        "schedule-advanced", year, Semester.localize(semester_type), slug
    )


def select_lectures(request, year, semester_type, slug):
    """Handle selection of lectures to hide"""

    if request.method == "POST":
        with transaction.atomic():
            excludes = request.POST.getlist("exclude")

            subscriptions = Subscription.objects.get_subscriptions(
                year, semester_type, slug
            )

            for subscription in subscriptions:
                if excludes:
                    subscription.exclude.set(
                        subscription.course.lecture_set.filter(id__in=excludes)
                    )
                else:
                    subscription.exclude.clear()

                subscription.save()  # Trigger last_modified update

        utils.clear_cache(year, semester_type, slug)

    return shortcuts.redirect(
        "schedule-advanced", year, Semester.localize(semester_type), slug
    )


def api(request):
    key = "global-stats"

    response = cache.get(key)
    if response and not utils.should_bypass_cache(request):
        return response

    summary = SubscriptionsCount.objects.values_list("count", "date")

    count: int
    date: datetime.date
    epoch = datetime.datetime.fromtimestamp(0).date()

    days_encoder = encoding.DeltaDeltaEncoder()
    counts_encoder = encoding.DeltaDeltaEncoder()

    result: list[str] = []

    for count, date in summary:
        d = encoding.zig_zag_encode(days_encoder.encode((date - epoch).days))
        c = encoding.zig_zag_encode(counts_encoder.encode(count))

        if d == 0:
            result.append(f"{c}")
        else:
            result.append(f"{d}:{c}")

    cache_timeout = datetime.timedelta(hours=12)
    response = http.HttpResponse(
        ",".join(result).encode(),
        content_type="text/plain",
        headers=utils.cache_headers(cache_timeout),
    )
    cache.set(key, response, cache_timeout.total_seconds())

    if settings.DEBUG and "html" in request.GET:
        return utils.debug_response(response)
    return response


def about(request):
    return shortcuts.render(request, "about.html")
