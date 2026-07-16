import datetime
import subprocess
import tempfile
from pathlib import Path
from unittest import mock

import pytest
from lxml import html

from django.conf import settings
from django.core.cache import cache, caches
from django.db.models import Value
from django.test import override_settings
from django.urls import reverse as django_reverse
from django.utils import http as http_utils
from django.utils import timezone
from django.utils.datastructures import MultiValueDict

from plan.common import views
from plan.common.models import (
    Course,
    Group,
    Lecture,
    Schedule,
    Semester,
    Student,
    Subscription,
)
from plan.common.snapshot import ScheduleSnapshot, schedule_snapshot_cache_key
from plan.common.tests import strict_template_variables

FIXTURE_LECTURE_ID = 12
pytestmark = pytest.mark.django_db


def test_empty_index(client):
    response = client.get(django_reverse("frontpage"))
    assert response.status_code == 404
    assert "404.html" in [template.name for template in response.templates]


def test_empty_shortcut(client):
    response = client.get(django_reverse("shortcut", args=["adamcik"]))
    assert response.status_code == 404
    assert "404.html" in [template.name for template in response.templates]


def test_robots_txt(client):
    response = client.get("/robots.txt")
    assert response.status_code == 200
    assert "User-agent: *".encode() in response.content
    assert "Disallow: /*/*/*/".encode() in response.content
    assert "Disallow: /*/*/*/*".encode() in response.content


def test_favicon(client):
    response = client.get("/favicon.ico")
    assert response.status_code == 301
    assert response["Location"].endswith("/static/favicon.png")


@override_settings(TIMETABLE_REPORT_URI="https://reports.example/csp")
def test_csp_reporting_endpoint(client):
    response = client.get("/")
    assert response.status_code == 404
    assert response["Reporting-Endpoints"] == 'endpoint="https://reports.example/csp"'
    assert (
        "report-uri https://reports.example/csp" in response["Content-Security-Policy"]
    )
    assert "report-to endpoint" in response["Content-Security-Policy"]


def test_index(
    client, serialized_schedule_data, cache_isolation, frozen_time, schedule_scenario
):
    response = client.get(django_reverse("frontpage"))
    url = django_reverse("semester", args=[schedule_scenario.semester])
    assert response.status_code == 302
    assert response["Location"] == url


def test_shortcut(
    client,
    serialized_schedule_data,
    cache_isolation,
    frozen_time,
    schedule_scenario,
    schedule_url,
):
    response = client.get(schedule_url("shortcut", "adamcik"))
    url = _schedule_reverse(schedule_scenario, "schedule-week", 1)
    assert response.status_code == 302
    assert response["Location"] == url


def test_redirect_room_missing_returns_404(client):
    response = client.get(django_reverse("redirect_room", args=[999999]))
    assert response.status_code == 404
    assert "404.html" in [template.name for template in response.templates]


def test_redirect_missing_returns_404_for_all_types(
    client, serialized_schedule_data, cache_isolation, frozen_time
):
    for name in (
        "redirect_room",
        "redirect_course",
        "redirect_syllabus",
        "redirect_stream",
    ):
        response = client.get(django_reverse(name, args=[999999]))
        assert response.status_code == 404
        assert "404.html" in [template.name for template in response.templates]


def test_schedule_current(
    client, serialized_schedule_data, cache_isolation, frozen_time, schedule_scenario
):
    url = _schedule_reverse(schedule_scenario, "schedule-current")
    response = client.get(url)
    assert response.status_code == 302
    assert response["Location"] == _schedule_reverse(
        schedule_scenario, "schedule-week", 1
    )
    response = client.get(
        django_reverse(
            "schedule-current",
            args=[
                schedule_scenario.next_schedule.semester,
                schedule_scenario.next_schedule.student.slug,
            ],
        )
    )
    assert response.status_code == 302
    assert response["Location"] == django_reverse(
        "schedule",
        args=[
            schedule_scenario.next_schedule.semester,
            schedule_scenario.next_schedule.student.slug,
        ],
    )


def test_getting_started_post_redirects_to_current_schedule(
    client, serialized_schedule_data, cache_isolation, frozen_time, schedule_scenario
):
    response = client.post(
        django_reverse("semester", args=[schedule_scenario.semester]),
        {"slug": schedule_scenario.student.slug},
    )
    assert response.status_code == 302
    assert response["Location"] == _schedule_reverse(
        schedule_scenario, "schedule-week", 1
    )


def test_unknown_semester_name_returns_404(
    client, serialized_schedule_data, cache_isolation, frozen_time
):
    response = client.get("/2009/winter/")
    assert response.status_code == 404


def test_semester_alias_redirects_to_canonical_slug(
    client, serialized_schedule_data, cache_isolation, frozen_time
):
    for alias in ("autum", "autmn", "autumn"):
        response = client.get(f"/2026/{alias}/")
        assert response.status_code == 301
        assert response["Location"] == "/2026/fall/"


def test_schedule(
    client, serialized_schedule_data, cache_isolation, frozen_time, schedule_scenario
):
    for url in [
        _schedule_reverse(schedule_scenario, "schedule"),
        _schedule_reverse(schedule_scenario, "schedule-advanced"),
        _schedule_reverse(schedule_scenario, "schedule-week", 1),
        _schedule_reverse(schedule_scenario, "schedule-week", 2),
        _schedule_reverse(schedule_scenario, "schedule"),
    ]:
        response = client.get(url)
        assert response.status_code == 200
        assert "schedule.html" in [template.name for template in response.templates]


@override_settings(
    TIMETABLE_LOCATION_CACHE_TTL=123,
    TIMETABLE_SCHEDULE_DATA_CACHE_TTL=456,
    TIMETABLE_COURSE_STATS_CACHE_TTL=789,
)
def test_primary_cache_writes_use_configured_ttls(
    client, serialized_schedule_data, cache_isolation, frozen_time
):
    cache.clear()
    semester = Semester.objects.get(year=2009, type=Semester.SPRING)
    student = Student.objects.get(slug="adamcik")
    snapshot = ScheduleSnapshot(semester=semester, student=student, last_modified=1)
    with mock.patch("plan.common.views.cache.set") as view_cache_set:
        views._common_data()
        views._schedule_data(snapshot)
    view_cache_set.assert_any_call("locations-next_semester", mock.ANY, 123)
    view_cache_set.assert_any_call(
        f"data:schedule:{snapshot.freshness_key()}", mock.ANY, timeout=456
    )
    with mock.patch("plan.common.models.cache.set") as model_cache_set:
        Course.get_stats(semester)
    model_cache_set.assert_called_once_with(mock.ANY, mock.ANY, 789)


def test_schedule_renders_lecture_and_course_classes_and_room_links(
    client, serialized_schedule_data, cache_isolation, frozen_time, schedule_scenario
):
    semester = Semester.objects.get(year=2009, type=Semester.SPRING)
    student = Student.objects.get(slug="adamcik")
    response = client.get(_schedule_reverse(schedule_scenario, "schedule"))
    assert response.status_code == 200
    lectures = Lecture.objects.get_lectures_data(semester.id, student.id)
    lecture = next(
        (item for item in lectures if item.lecture_id == FIXTURE_LECTURE_ID), None
    )
    assert lecture is not None
    assert f"lecture-{lecture.lecture_id}".encode() in response.content
    assert f"course-{lecture.course_id}".encode() in response.content


@strict_template_variables()
def test_schedule_renders_without_missing_template_variables(
    client, serialized_schedule_data, cache_isolation, frozen_time, schedule_scenario
):
    response = client.get(_schedule_reverse(schedule_scenario, "schedule"))
    assert response.status_code == 200
    assert "schedule.html" in [template.name for template in response.templates]


@strict_template_variables()
def test_schedule_advanced_renders_without_missing_template_variables(
    client, serialized_schedule_data, cache_isolation, frozen_time, schedule_scenario
):
    response = client.get(_schedule_reverse(schedule_scenario, "schedule-advanced"))
    assert response.status_code == 200
    assert "schedule.html" in [template.name for template in response.templates]


def test_schedule_sets_robots_header(
    client, serialized_schedule_data, cache_isolation, frozen_time, schedule_scenario
):
    response = client.get(_schedule_reverse(schedule_scenario, "schedule"))
    assert response.headers["X-Robots-Tag"] == "noindex, nofollow, noarchive"


def test_schedule_sets_etag_header(
    client, serialized_schedule_data, cache_isolation, frozen_time, schedule_scenario
):
    response = client.get(_schedule_reverse(schedule_scenario, "schedule"))
    assert response.status_code == 200
    assert "ETag" in response.headers


@override_settings(INSTALLED_APPS=(*settings.INSTALLED_APPS, "debug_toolbar"))
def test_schedule_etag_varies_with_debug_toolbar(
    client, serialized_schedule_data, cache_isolation, frozen_time, schedule_scenario
):
    response = client.get(_schedule_reverse(schedule_scenario, "schedule"))
    assert response.headers["ETag"].endswith('-debug"')


def test_rendered_html_is_valid_html5(
    client, serialized_schedule_data, cache_isolation, frozen_time, schedule_scenario
):
    pages = {
        "start.html": client.get(
            django_reverse("semester", args=[schedule_scenario.semester])
        ),
        "about.html": client.get(django_reverse("about")),
        "schedule.html": client.get(_schedule_reverse(schedule_scenario, "schedule")),
        "schedule-advanced.html": client.get(
            _schedule_reverse(schedule_scenario, "schedule-advanced")
        ),
        "select_groups.html": client.get(
            _schedule_reverse(schedule_scenario, "change-groups")
        ),
        "error.html": client.post(
            _schedule_reverse(schedule_scenario, "change-course"),
            {"submit_add": True, "course_add": "NOT_A_REAL_COURSE"},
        ),
    }
    _assert_valid_html5(pages)


def test_schedule_if_none_match_returns_304(
    client, serialized_schedule_data, cache_isolation, frozen_time, schedule_scenario
):
    url = _schedule_reverse(schedule_scenario, "schedule")
    first = client.get(url)
    second = client.get(url, HTTP_IF_NONE_MATCH=first.headers["ETag"])
    assert second.status_code == 304
    assert second.content == b""
    assert "Content-Language" not in second.headers


def test_schedule_if_none_match_takes_precedence_over_if_modified_since(
    client, serialized_schedule_data, cache_isolation, frozen_time, schedule_scenario
):
    url = _schedule_reverse(schedule_scenario, "schedule")
    first = client.get(url)
    response = client.get(
        url,
        HTTP_IF_NONE_MATCH='"does-not-match"',
        HTTP_IF_MODIFIED_SINCE=first.headers.get("Last-Modified", ""),
    )
    assert response.status_code == 200


def test_change_course(
    client, serialized_schedule_data, cache_isolation, frozen_time, schedule_scenario
):
    original_url = _schedule_reverse(schedule_scenario, "schedule-advanced")
    url = _schedule_reverse(schedule_scenario, "change-course")
    post_data = [
        {"submit_add": True, "course_add": "COURSE4"},
        {"submit_name": True, "4-alias": "foo"},
        {
            "submit_name": True,
            "4-alias": "foo bar baz foo bar baz foo bar baz "
            + "foo bar baz foo bar baz foo bar baz",
        },
        {"submit_remove": True, "course_remove": 4},
    ]
    subscriptions = Subscription.objects.filter(student__slug="adamcik")
    subscriptions = subscriptions.order_by("id").values_list()
    subscriptions = list(subscriptions)
    for data in post_data:
        client.get(original_url)
        response = client.post(url, data)
        assert response.status_code == 302
        new_subscriptions = list(
            Subscription.objects.filter(student__slug="adamcik")
            .order_by("id")
            .values_list()
        )
        assert new_subscriptions != subscriptions
        subscriptions = new_subscriptions


def test_change_course_add_empty_input_redirects_to_schedule_advanced(
    client, serialized_schedule_data, cache_isolation, frozen_time, schedule_scenario
):
    response = client.post(
        _schedule_reverse(schedule_scenario, "change-course"),
        {"submit_add": True, "course_add": ""},
    )
    assert response.status_code == 302
    assert response["Location"] == _schedule_reverse(
        schedule_scenario, "schedule-advanced"
    )


@override_settings(TIMETABLE_ENABLE_IF_MODIFIED_SINCE=True)
def test_change_course_remove_invalidates_schedule_data_cache(
    client,
    serialized_schedule_data,
    cache_isolation,
    frozen_time,
    schedule_scenario,
):
    schedule_url = _schedule_reverse(schedule_scenario, "schedule-advanced")
    change_url = _schedule_reverse(schedule_scenario, "change-course")
    subscriptions = Subscription.objects.filter(
        student__slug="adamcik",
        course__semester__year=2009,
        course__semester__type="spring",
    ).order_by("course__id")
    assert subscriptions.count() >= 2
    remove_course_id = subscriptions.last().course_id
    remove_course_code = subscriptions.last().course.code
    shared_last_modified = timezone.make_aware(datetime.datetime(2009, 1, 1, 12, 0, 0))
    subscriptions.update(last_modified=shared_last_modified)
    cache.clear()
    response = client.get(schedule_url)
    assert response.status_code == 200
    assert remove_course_code.encode() in response.content
    assert "Last-Modified" in response.headers
    if_modified_since = response.headers["Last-Modified"]
    response = client.post(
        change_url, {"submit_remove": True, "course_remove": str(remove_course_id)}
    )
    assert response.status_code == 302
    response = client.get(schedule_url, HTTP_IF_MODIFIED_SINCE=if_modified_since)
    assert response.status_code == 200
    assert remove_course_code.encode() not in response.content


@override_settings(TIMETABLE_ENABLE_IF_MODIFIED_SINCE=True)
def test_change_course_in_other_semester_does_not_invalidate_current_schedule(
    client, serialized_schedule_data, cache_isolation, frozen_time, schedule_scenario
):
    spring_schedule_url = _schedule_reverse(schedule_scenario, "schedule-advanced")
    fall_change_url = django_reverse(
        "change-course",
        args=[
            schedule_scenario.next_schedule.semester,
            schedule_scenario.next_schedule.student.slug,
        ],
    )
    response = client.get(spring_schedule_url)
    assert response.status_code == 200
    assert "Last-Modified" in response.headers
    if_modified_since = response.headers["Last-Modified"]
    response = client.post(
        fall_change_url, {"submit_add": True, "course_add": "COURSE4"}
    )
    assert response.status_code == 302
    response = client.get(spring_schedule_url, HTTP_IF_MODIFIED_SINCE=if_modified_since)
    assert response.status_code == 304


@override_settings(TIMETABLE_ENABLE_IF_MODIFIED_SINCE=True)
def test_schedule_if_modified_since_returns_304_after_change_course_mutation(
    client,
    serialized_schedule_data,
    cache_isolation,
    frozen_time,
    schedule_scenario,
):
    schedule_url = _schedule_reverse(schedule_scenario, "schedule-advanced")
    change_url = _schedule_reverse(schedule_scenario, "change-course")
    response = client.get(schedule_url)
    assert response.status_code == 200
    assert "Last-Modified" in response.headers
    if_modified_since = response.headers["Last-Modified"]
    response = client.post(change_url, {"submit_add": True, "course_add": "COURSE4"})
    assert response.status_code == 302
    response = client.get(schedule_url, HTTP_IF_MODIFIED_SINCE=if_modified_since)
    assert response.status_code == 200


def test_change_course_creates_schedule_row_with_version_bump(
    client,
    serialized_schedule_data,
    cache_isolation,
    frozen_time,
    schedule_scenario,
):
    schedule_url = _schedule_reverse(schedule_scenario, "schedule-advanced")
    change_url = _schedule_reverse(schedule_scenario, "change-course")
    Schedule.objects.filter(
        semester__year=2009, semester__type="spring", student__slug="adamcik"
    ).delete()
    client.get(schedule_url)
    response = client.post(change_url, {"submit_add": True, "course_add": "COURSE4"})
    assert response.status_code == 302
    row = Schedule.objects.get(
        semester__year=2009, semester__type="spring", student__slug="adamcik"
    )
    assert row.version == 1


def test_change_course_increments_schedule_version_on_each_mutation(
    client,
    serialized_schedule_data,
    cache_isolation,
    frozen_time,
    schedule_scenario,
):
    schedule_url = _schedule_reverse(schedule_scenario, "schedule-advanced")
    change_url = _schedule_reverse(schedule_scenario, "change-course")
    student = Student.objects.get(slug="adamcik")
    semester = Semester.objects.get(year=2009, type="spring")
    row, _ = Schedule.objects.get_or_create(
        semester_id=semester.id, student_id=student.id, defaults={"version": 0}
    )
    row.version = 0
    row.save(update_fields=["version"])
    client.get(schedule_url)
    response = client.post(change_url, {"submit_add": True, "course_add": "COURSE4"})
    assert response.status_code == 302
    row.refresh_from_db()
    assert row.version == 1
    remove_course_id = Subscription.objects.get(
        student__slug="adamcik",
        course__semester__year=2009,
        course__semester__type="spring",
        course__code="COURSE4",
    ).course_id
    response = client.post(
        change_url, {"submit_remove": True, "course_remove": str(remove_course_id)}
    )
    assert response.status_code == 302
    row.refresh_from_db()
    assert row.version == 2


def test_back_to_back_mutations_advance_last_modified_for_ims(
    client,
    serialized_schedule_data,
    cache_isolation,
    frozen_time,
    schedule_scenario,
):
    schedule_url = _schedule_reverse(schedule_scenario, "schedule-advanced")
    change_url = _schedule_reverse(schedule_scenario, "change-course")
    fixed_time = timezone.make_aware(datetime.datetime(2026, 1, 1, 12, 0, 0))
    with mock.patch("plan.common.snapshot.Now", return_value=Value(fixed_time)):
        response = client.post(
            change_url, {"submit_add": True, "course_add": "COURSE4"}
        )
        assert response.status_code == 302
        first = client.get(schedule_url)
        assert first.status_code == 200
        course_id = Subscription.objects.get(
            student__slug="adamcik",
            course__semester__year=2009,
            course__semester__type="spring",
            course__code="COURSE4",
        ).course_id
        response = client.post(
            change_url, {"submit_remove": True, "course_remove": str(course_id)}
        )
        assert response.status_code == 302
    second = client.get(schedule_url)
    assert http_utils.parse_http_date(
        second.headers["Last-Modified"]
    ) > http_utils.parse_http_date(first.headers["Last-Modified"])
    response = client.get(
        schedule_url, HTTP_IF_MODIFIED_SINCE=first.headers["Last-Modified"]
    )
    assert response.status_code == 200


def test_change_course_updates_schedule_last_modified_on_existing_row(
    client,
    serialized_schedule_data,
    cache_isolation,
    frozen_time,
    schedule_scenario,
):
    schedule_url = _schedule_reverse(schedule_scenario, "schedule-advanced")
    change_url = _schedule_reverse(schedule_scenario, "change-course")
    student = Student.objects.get(slug="adamcik")
    semester = Semester.objects.get(year=2009, type="spring")
    row, _ = Schedule.objects.get_or_create(
        semester_id=semester.id, student_id=student.id, defaults={"version": 0}
    )
    baseline = timezone.make_aware(datetime.datetime(2009, 1, 1, 12, 0, 0))
    Schedule.objects.filter(id=row.id).update(version=0, last_modified=baseline)
    client.get(schedule_url)
    response = client.post(change_url, {"submit_add": True, "course_add": "COURSE4"})
    assert response.status_code == 302
    row.refresh_from_db()
    assert row.version == 1
    assert row.last_modified > baseline


@override_settings(TIMETABLE_ENABLE_IF_MODIFIED_SINCE=True)
def test_delete_mutation_returns_200_for_old_if_modified_since(
    client,
    serialized_schedule_data,
    cache_isolation,
    frozen_time,
    schedule_scenario,
):
    schedule_url = _schedule_reverse(schedule_scenario, "schedule-advanced")
    change_url = _schedule_reverse(schedule_scenario, "change-course")
    response = client.get(schedule_url)
    assert response.status_code == 200
    old_if_modified_since = response.headers["Last-Modified"]
    remove_course_id = (
        Subscription.objects.filter(
            student__slug="adamcik",
            course__semester__year=2009,
            course__semester__type="spring",
        )
        .order_by("course_id")
        .values_list("course_id", flat=True)
        .first()
    )
    assert remove_course_id is not None
    response = client.post(
        change_url, {"submit_remove": True, "course_remove": str(remove_course_id)}
    )
    assert response.status_code == 302
    response = client.get(schedule_url, HTTP_IF_MODIFIED_SINCE=old_if_modified_since)
    assert response.status_code == 200


@override_settings(
    TIMETABLE_ENABLE_IF_MODIFIED_SINCE=True,
    TIMETABLE_SNAPSHOT_CACHE_DISK_TTL=7 * 24 * 60 * 60,
)
def test_change_course_invalidates_disk_backed_snapshot_metadata(
    client,
    serialized_schedule_data,
    cache_isolation,
    frozen_time,
    schedule_scenario,
):
    schedule_url = _schedule_reverse(schedule_scenario, "schedule-advanced")
    change_url = _schedule_reverse(schedule_scenario, "change-course")
    snapshot_key = schedule_snapshot_cache_key(
        schedule_scenario.semester, schedule_scenario.student.slug
    )
    response = client.get(schedule_url)
    assert response.status_code == 200
    assert "Last-Modified" in response.headers
    old_if_modified_since = response.headers["Last-Modified"]
    assert caches["disk"].get(snapshot_key) is not None
    caches["default"].clear()
    response = client.post(change_url, {"submit_add": True, "course_add": "COURSE4"})
    assert response.status_code == 302
    assert caches["disk"].get(snapshot_key) is None
    response = client.get(schedule_url, HTTP_IF_MODIFIED_SINCE=old_if_modified_since)
    assert response.status_code == 200


def test_schedule_with_warm_cache_force_reload_makes_no_queries(
    client,
    serialized_schedule_data,
    cache_isolation,
    frozen_time,
    schedule_scenario,
    django_assert_num_queries,
):
    schedule_url = _schedule_reverse(schedule_scenario, "schedule")
    cache.clear()
    response = client.get(schedule_url)
    assert response.status_code == 200
    with django_assert_num_queries(0):
        response = client.get(schedule_url, HTTP_CACHE_CONTROL="no-cache")
    assert response.status_code == 200


@override_settings(TIMETABLE_SCHEDULE_CACHE_DURATION=datetime.timedelta(seconds=60))
def test_schedule_cache_hit_preserves_csp_nonces(
    client,
    serialized_schedule_data,
    cache_isolation,
    frozen_time,
    schedule_scenario,
):

    def csp_nonce(policy: str, directive: str) -> str | None:
        for part in policy.split(";"):
            tokens = part.split()
            if not tokens or tokens[0] != directive:
                continue
            for token in tokens[1:]:
                if token.startswith("'nonce-") and token.endswith("'"):
                    return token[len("'nonce-") : -1]
        return None

    schedule_url = _schedule_reverse(schedule_scenario, "schedule")
    cache.clear()
    caches["disk"].clear()
    first = client.get(schedule_url)
    assert first.status_code == 200
    assert "miss" in first.headers["X-Cache"]
    second = client.get(schedule_url)
    assert second.status_code == 200
    assert "hit" in second.headers["X-Cache"]
    policy = second.headers["Content-Security-Policy"]
    script_nonce = csp_nonce(policy, "script-src")
    style_nonce = csp_nonce(policy, "style-src")
    assert script_nonce is not None
    assert style_nonce is not None
    document = html.fromstring(second.content)
    script_nonces = set(document.xpath("//script[@nonce]/@nonce"))
    style_nonces = set(document.xpath("//style[@nonce]/@nonce"))
    assert script_nonce in script_nonces
    assert style_nonce in style_nonces


def test_schedule_week_with_warm_cache_force_reload_makes_no_queries(
    client,
    serialized_schedule_data,
    cache_isolation,
    frozen_time,
    schedule_scenario,
    django_assert_num_queries,
):
    schedule_week_url = _schedule_reverse(schedule_scenario, "schedule-week", 1)
    cache.clear()
    response = client.get(schedule_week_url)
    assert response.status_code == 200
    with django_assert_num_queries(0):
        response = client.get(schedule_week_url, HTTP_CACHE_CONTROL="no-cache")
    assert response.status_code == 200


def test_schedule_force_reload_week_after_non_week_warm_makes_no_queries(
    client,
    serialized_schedule_data,
    cache_isolation,
    frozen_time,
    schedule_scenario,
    django_assert_num_queries,
):
    schedule_url = _schedule_reverse(schedule_scenario, "schedule")
    schedule_week_url = _schedule_reverse(schedule_scenario, "schedule-week", 1)
    cache.clear()
    response = client.get(schedule_url)
    assert response.status_code == 200
    with django_assert_num_queries(0):
        response = client.get(schedule_week_url, HTTP_CACHE_CONTROL="no-cache")
    assert response.status_code == 200


def test_schedule_force_reload_non_week_after_week_warm_makes_no_queries(
    client,
    serialized_schedule_data,
    cache_isolation,
    frozen_time,
    schedule_scenario,
    django_assert_num_queries,
):
    schedule_url = _schedule_reverse(schedule_scenario, "schedule")
    schedule_week_url = _schedule_reverse(schedule_scenario, "schedule-week", 1)
    cache.clear()
    response = client.get(schedule_week_url)
    assert response.status_code == 200
    with django_assert_num_queries(0):
        response = client.get(schedule_url, HTTP_CACHE_CONTROL="no-cache")
    assert response.status_code == 200


def test_change_course_invalid_course_renders_error(
    client, serialized_schedule_data, cache_isolation, frozen_time, schedule_scenario
):
    url = _schedule_reverse(schedule_scenario, "change-course")
    response = client.post(url, {"submit_add": True, "course_add": "NOT_A_REAL_COURSE"})
    assert response.status_code == 200
    assert "error.html" in [template.name for template in response.templates]


def test_change_groups(
    client, serialized_schedule_data, cache_isolation, frozen_time, schedule_scenario
):
    original_url = _schedule_reverse(schedule_scenario, "schedule-advanced")
    url = _schedule_reverse(schedule_scenario, "change-groups")
    post_data = [
        {"1-groups": "1", "2-groups": "", "3-groups": "2"},
        {"1-groups": "", "2-groups": "", "3-groups": ""},
        {"1-groups": ("1", "2"), "2-groups": "", "3-groups": "2"},
    ]
    groups = list(
        Group.objects.filter(subscription__student__slug="adamcik")
        .order_by("id")
        .values_list()
    )
    for data in post_data:
        client.get(original_url)
        response = client.post(url, MultiValueDict(data))
        assert response["Location"].endswith(original_url)
        assert response.status_code == 302
        new_groups = list(
            Group.objects.filter(subscription__student__slug="adamcik")
            .order_by("id")
            .values_list()
        )
        assert groups != new_groups
        groups = new_groups


def test_change_lectures(
    client, serialized_schedule_data, cache_isolation, frozen_time, schedule_scenario
):
    original_url = _schedule_reverse(schedule_scenario, "schedule-advanced")
    url = _schedule_reverse(schedule_scenario, "change-lectures")
    post_data = [
        {"exclude": ("2", "3", "8")},
        {"exclude": "2"},
        {"exclude": ("2", "3", "8", "9", "7", "10", "11", "4", "5", "6")},
        {"exclude": "2"},
        {"exclude": ("2", "3", "8")},
    ]
    lectures = list(
        Lecture.objects.filter(excluded_from__student__slug="adamcik")
        .order_by("id")
        .values_list()
    )
    for data in post_data:
        client.get(original_url)
        response = client.post(url, MultiValueDict(data))
        assert response["Location"].endswith(original_url)
        assert response.status_code == 302
        new_lectures = list(
            Lecture.objects.filter(excluded_from__student__slug="adamcik")
            .order_by("id")
            .values_list()
        )
        assert lectures != new_lectures
        lectures = new_lectures


def test_course_query(
    client, serialized_schedule_data, cache_isolation, frozen_time, schedule_scenario
):
    url = django_reverse("course-query", args=[schedule_scenario.semester])
    response = client.get(url)
    assert b"" == response.content
    response = client.get(url, {"q": "COURSE"})
    lines = response.content.split(b"\n")
    assert b"COURSE1|Course 1 full name" == lines[0]
    assert b"COURSE2|Course 2 full name" == lines[1]
    assert b"COURSE3|Course 3 full name" == lines[2]
    assert b"COURSE4|Course 4 full name" == lines[3]
    response = client.get(url, {"q": "COURSE", "limit": 2})
    lines = [line for line in response.content.split(b"\n") if line]
    assert 2 == len(lines)
    response = client.get(
        url, {"q": "COURSE", "limit": 2}, HTTP_ACCEPT="application/json"
    )
    assert 2 == len(response.json())


def _schedule_reverse(schedule_scenario, view_name, *extra_args):
    return django_reverse(
        view_name,
        args=[
            schedule_scenario.semester,
            schedule_scenario.student.slug,
            *extra_args,
        ],
    )


def _assert_valid_html5(pages):
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        for filename, response in pages.items():
            assert response.status_code == 200, (
                f"expected 200 for {filename}, got {response.status_code}"
            )
            (root / filename).write_bytes(response.content)
        result = subprocess.run(
            ["html5validator", "--root", tmpdir, "--match", "*.html"],
            check=False,
            capture_output=True,
            text=True,
        )
    assert result.returncode == 0, (
        f"html5validator failed:\n{result.stdout}{result.stderr}"
    )
