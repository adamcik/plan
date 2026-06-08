# This file is part of the plan timetable generator, see LICENSE for details.

import datetime
import json
from typing import Optional

from django import http, shortcuts
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
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
from plan.common.schedule import Schedule
from plan.common.snapshot import (
    ScheduleSnapshot,
    ScheduleSnapshotNotFound,
    bump_snapshot,
    get_schedule_snapshot,
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


def robots_txt(request):
    content = "\n".join(
        [
            "User-agent: *",
            "Disallow: /*/*/*/",
            "Disallow: /*/*/*/*",
        ]
    )
    return http.HttpResponse(f"{content}\n", content_type="text/plain")


# Start new week on saturdays
def get_current_week():
    return (now() + datetime.timedelta(days=2)).isocalendar()[1]


@utils.expires_in(datetime.timedelta(hours=1))
def frontpage(request):
    try:
        semester = Semester.objects.active()
    except Semester.DoesNotExist:
        raise http.Http404
    return shortcuts.redirect("semester", semester)


@utils.expires_in(datetime.timedelta(hours=1))
def shortcut(request, slug):
    """Redirect users to their timetable for the current semester"""
    try:
        semester = Semester.objects.active()
    except Semester.DoesNotExist:
        raise http.Http404
    return schedule_current(request, semester, slug)


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
    except (Room.DoesNotExist, Course.DoesNotExist, Lecture.DoesNotExist):
        raise http.Http404

    if not url:
        raise http.Http404

    if settings.TIMETABLE_UTM_SOURCE:
        url = utils.update_url_params(
            url, {"utm_source": settings.TIMETABLE_UTM_SOURCE}
        )
    return shortcuts.redirect(url)


@utils.expires_in(datetime.timedelta(hours=1))
def getting_started(request, semester):
    """Initial top level page that greets users"""
    try:
        semester = Semester.objects.get(year=semester.year, type=semester.type)
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
            # TODO(adamcik): what should we do if current is empty?
            return schedule_current(
                request,
                semester,
                schedule_form.cleaned_data["slug"],
            )
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


def course_query(request, semester):
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
            semester.year,
            semester.type,
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
    return response


def schedule_current(request, semester: Semester, slug: str):
    try:
        snapshot = get_schedule_snapshot(semester, slug)
    except ScheduleSnapshotNotFound:
        raise http.Http404

    current_week = get_current_week()

    # NOTE: We use the slug to allow for students that don't yet exist.
    weeks = Week.objects.filter(
        lecture__course__subscription__student__slug=snapshot.student.slug,
        lecture__course__semester=snapshot.semester,
    )
    weeks = weeks.distinct().values_list("number", flat=True)

    if current_week in weeks and snapshot.semester.year == today().year:
        return shortcuts.redirect(
            "schedule-week", snapshot.semester, snapshot.student.slug, current_week
        )
    return shortcuts.redirect("schedule", snapshot.semester, snapshot.student.slug)


def _common_data():
    key = "locations-next_semester"
    result = cache.get(key)
    if result:
        return result

    locations = Location.objects.distinct()  # .filter(course__semester=semester)
    try:
        next_semester = next(Semester.objects)
    except Semester.DoesNotExist:
        next_semester = None

    cache.set(key, (locations, next_semester), 3600)
    return locations, next_semester


def _schedule_data(s: Schedule, next_semester: Optional[Semester] = None):
    if s.last_modified is None:
        return [], [], [], [], [], [], [], []

    key = f"data:schedule:{s.freshness_key()}"
    result = cache.get(key)
    if result:
        return result

    courses = list(
        Course.objects.filter(
            subscription__student=s.student.id,
            subscription__course__semester=s.semester,
        )
        .extra(select={"alias": "common_subscription.alias"})
        .distinct()
        .order_by("code")
    )

    lectures = Lecture.objects.get_lectures_data(
        s.semester.id,
        s.student.id,
    )

    # Most of these could be built into get_lectures_data with ARRAY_AGG..
    exams = {}
    for exam in (
        Exam.objects.filter(course__in=courses)
        .select_related("course", "type")
        .order_by("handout_date", "handout_time", "exam_date", "exam_time")
    ):
        exams.setdefault(exam.course_id, []).append(exam)

    # Use get_related to cut query counts
    lecturers = []  # Lecture.get_related(Lecturer, lectures)
    lecture_ids = [lecture.lecture_id for lecture in lectures]
    groups = Lecture.get_related(Group, lecture_ids, fields=["code"])
    rooms = Lecture.get_related(Room, lecture_ids, fields=["id", "name", "url"])

    schedule_weeks = set()
    for l in lectures:
        schedule_weeks.update(l.week_numbers)
    if schedule_weeks:
        schedule_weeks = list(range(min(schedule_weeks), max(schedule_weeks) + 1))

    if (
        next_semester
        and not Subscription.objects.get_subscriptions(
            next_semester.year, next_semester.type, s.student.slug
        ).exists()
    ):
        next_schedule = Schedule(
            semester=next_semester,
            student=s.student,
        )
    else:
        next_schedule = None

    # NOTE: This data can be used across pages, so cache it.

    # TODO: Should we consider a get_related for courses as well?
    # TODO: get_related duplicates data, perhaps the exams dict should just
    # be {lecture_id: exam_id} and then there is a {exam_id: exam} mapping?

    result = (
        lectures,
        courses,
        exams,
        lecturers,
        groups,
        rooms,
        schedule_weeks,
        next_schedule,
    )
    cache.set(key, result, timeout=3600)
    return result


def schedule(
    request,
    semester: Semester,
    slug: str,
    advanced: bool = False,
    week: int | None = None,
    all: bool = False,
):
    """Page that handles showing schedules"""
    try:
        snapshot = get_schedule_snapshot(semester, slug)
    except ScheduleSnapshotNotFound:
        raise http.Http404

    current_week = get_current_week()

    # Color mapping for the courses
    color_map = utils.ColorMap(hex=True)

    bypass_cache = utils.should_bypass_cache(request)
    route = str(request.resolver_match.url_name)
    path = request.path_info
    cache_key = utils.response_cache_key(route, snapshot.freshness_key(), path)
    headers = utils.build_validator_headers(
        cache_key=cache_key,
        last_modified=snapshot.last_modified,
        extra_headers={"X-Robots-Tag": "noindex, nofollow, noarchive"},
    )
    response = utils.check_not_modified(request, snapshot.last_modified, headers)
    if response:
        return response

    response = utils.lookup_cached_response(
        cache_alias="default",
        cache_key=cache_key,
        headers=headers,
        bypass=bypass_cache,
    )
    if response:
        return response

    locations, next_semester = _common_data()

    (
        lectures,
        courses,
        exams,
        lecturers,
        groups,
        rooms,
        schedule_weeks,
        next_schedule,
    ) = _schedule_data(snapshot, next_semester)

    # Check prev/next weeks:
    if week and week + 1 in schedule_weeks:
        next_week = week + 1
    else:
        next_week = None
    if week and week - 1 in schedule_weeks:
        prev_week = week - 1
    else:
        prev_week = None

    # Init colors in predictable maner
    for c in courses:
        color_map[c.id]

    # Create Timetable
    table = timetable.Timetable(lectures)
    if week:
        table.set_week(snapshot.semester.year, week)
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

    week_is_current = snapshot.semester.year == today().year and week == current_week

    # TODO: Natural sort course code? Why is this needed here?
    lectures.sort(
        key=lambda l: (
            l.course_code,
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
            "lectures": lectures,
            "semester": snapshot.semester,
            "week_is_current": week_is_current,
            "next_semester": next_semester,
            "slug": snapshot.student.slug,
            "timetable": table,
            "week": week,
            "next_week": next_week,
            "prev_week": prev_week,
            "rooms": rooms,
            "groups": groups,
            "lecturers": lecturers,
            "locations": locations,
            "weeks": schedule_weeks,
            "schedule": snapshot,
            "next_schedule": next_schedule,
        },
    )

    utils.apply_response_headers(response, headers)
    CspMiddleware.store_nonce_in_header(request, response)
    timeout = None
    if settings.TIMETABLE_SCHEDULE_CACHE_DURATION is not None:
        timeout = settings.TIMETABLE_SCHEDULE_CACHE_DURATION.total_seconds()

    return utils.store_cached_response(
        cache_alias="default",
        cache_key=cache_key,
        response=response,
        timeout=timeout,
        bypass=bypass_cache,
    )


def select_groups(request, semester: Semester, slug: str):
    """Form handler for selecting groups to use in schedule"""
    try:
        snapshot = get_schedule_snapshot(semester, slug)
    except ScheduleSnapshotNotFound:
        raise http.Http404

    courses = Course.objects.get_courses(
        snapshot.semester.year,
        snapshot.semester.type,
        snapshot.student.slug,
    )
    course_groups = Course.get_groups(
        snapshot.semester.year,
        snapshot.semester.type,
        [c.id for c in courses],
    )

    if request.method == "POST":
        with transaction.atomic():
            changed = False
            for c in courses:
                try:
                    groups = course_groups[c.id]
                except KeyError:  # Skip courses without groups
                    continue

                group_form = forms.GroupForm(groups, request.POST, prefix=c.id)

                if group_form.is_valid():
                    subscription = Subscription.objects.get_subscriptions(
                        snapshot.semester.year,
                        snapshot.semester.type,
                        snapshot.student.slug,
                    ).get(course=c)

                    selected_groups = set(group_form.cleaned_data["groups"])
                    current_groups = set(subscription.groups.all())

                    if selected_groups != current_groups:
                        subscription.groups.set(group_form.cleaned_data["groups"])
                        subscription.save()  # Update last modified.
                        changed = True

            if changed:
                bump_snapshot(snapshot)

            utils.clear_cache(snapshot)

        return shortcuts.redirect(
            "schedule-advanced", snapshot.semester, snapshot.student.slug
        )

    color_map = utils.ColorMap(hex=True)
    subscription_groups = Subscription.get_groups(
        snapshot.semester.year,
        snapshot.semester.type,
        snapshot.student.slug,
    )
    all_subscripted_groups = set()

    for groups in subscription_groups.values():
        for group in groups:
            all_subscripted_groups.add(group)

    for c in courses:
        color_map[c.id]
        subscription_id = c.subscription_set.get(
            student__slug=snapshot.student.slug,
        ).pk

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
            "semester": snapshot.semester,
            "slug": snapshot.student.slug,
            "courses": courses,
            "color_map": color_map,
            "schedule": snapshot,
        },
    )


def select_course(request, semester: Semester, slug: str, add: bool = False):
    """Handle selecting of courses from course list, change of names and
    removeall of courses"""
    try:
        snapshot = get_schedule_snapshot(semester, slug)
    except ScheduleSnapshotNotFound:
        raise http.Http404

    if "submit_add" in request.POST or add:
        response = _add_courses(request, snapshot)
    elif "submit_remove" in request.POST:
        response = _remove_courses(request, snapshot)
    elif "submit_name" in request.POST:
        response = _override_name(request, snapshot)
    else:
        response = None

    utils.clear_cache(snapshot)
    if response:
        return response
    return shortcuts.redirect(
        "schedule-advanced", snapshot.semester, snapshot.student.slug
    )


def _add_courses(request, snapshot: ScheduleSnapshot):
    lookup = []

    for l in request.POST.getlist("course_add"):
        lookup.extend(l.replace(",", "").split())

    subscriptions = set(
        Subscription.objects.get_subscriptions(
            snapshot.semester.year,
            snapshot.semester.type,
            snapshot.student.slug,
        ).values_list("course__code", flat=True)
    )

    if not lookup:
        return shortcuts.redirect(
            "schedule-advanced",
            snapshot.semester,
            snapshot.student.slug,
        )

    errors = []
    too_many_subscriptions = False

    student, _ = Student.objects.get_or_create(slug=snapshot.student.slug)

    changed = False

    for l in lookup:
        try:
            if len(subscriptions) > settings.TIMETABLE_MAX_COURSES:
                too_many_subscriptions = True
                break

            course = Course.objects.get(
                code__iexact=l.strip(),
                semester=snapshot.semester,
            )

            _, created = Subscription.objects.get_or_create(
                student=student,
                course=course,
            )
            changed = changed or created
            subscriptions.add(course.code)

        except Course.DoesNotExist:
            errors.append(l)

    if errors or too_many_subscriptions:
        return shortcuts.render(
            request,
            "error.html",
            {
                "courses": errors,
                "max": settings.TIMETABLE_MAX_COURSES,
                "schedule": snapshot,
                "slug": snapshot.student.slug,
                "year": snapshot.semester.year,
                "type": snapshot.semester.type,
                "too_many_subscriptions": too_many_subscriptions,
            },
        )

    if changed:
        bump_snapshot(snapshot)

    return shortcuts.redirect("change-groups", snapshot.semester, snapshot.student.slug)


def _remove_courses(request, snapshot: ScheduleSnapshot):
    with transaction.atomic():
        courses = []
        for c in request.POST.getlist("course_remove"):
            if c.strip():
                courses.append(c.strip())

        deleted_count, _ = (
            Subscription.objects.get_subscriptions(
                snapshot.semester.year,
                snapshot.semester.type,
                snapshot.student.slug,
            )
            .filter(course__id__in=courses)
            .delete()
        )

        if deleted_count > 0:
            bump_snapshot(snapshot)

        slug = snapshot.student.slug
        if Subscription.objects.filter(student__slug=slug).count() == 0:
            Student.objects.filter(slug=slug).delete()

    return None


def _override_name(request, snapshot: ScheduleSnapshot):
    subscriptions = Subscription.objects.get_subscriptions(
        snapshot.semester.year,
        snapshot.semester.type,
        snapshot.student.slug,
    )

    changed = False

    for u in subscriptions:
        form = forms.CourseAliasForm(request.POST, prefix=u.course_id)

        if form.is_valid():
            alias = form.cleaned_data["alias"].strip()

            if alias.upper() == u.course.code.upper() or alias == "":
                # Leave as blank if we match the current course name
                alias = ""

            if u.alias != alias:
                u.alias = alias
                u.save()
                changed = True

    if changed:
        bump_snapshot(snapshot)

    return None


def select_lectures(request, semester: Semester, slug: str):
    """Handle selection of lectures to hide"""
    try:
        snapshot = get_schedule_snapshot(semester, slug)
    except ScheduleSnapshotNotFound:
        raise http.Http404

    if request.method == "POST":
        with transaction.atomic():
            excludes = request.POST.getlist("exclude")

            subscriptions = Subscription.objects.get_subscriptions(
                snapshot.semester.year,
                snapshot.semester.type,
                snapshot.student.slug,
            )

            for subscription in subscriptions:
                if excludes:
                    subscription.exclude.set(
                        subscription.course.lecture_set.filter(id__in=excludes)
                    )
                else:
                    subscription.exclude.clear()

                subscription.save()  # Trigger last_modified update

        utils.clear_cache(snapshot)
        bump_snapshot(snapshot)

    return shortcuts.redirect(
        "schedule-advanced", snapshot.semester, snapshot.student.slug
    )


def about(request):
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

    return shortcuts.render(
        request,
        "about.html",
        {"data": ",".join(result)},
    )
