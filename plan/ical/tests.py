# This file is part of the plan timetable generator, see LICENSE for details.

import datetime
from contextlib import nullcontext
from unittest import mock

import pytest
from django.utils import http as http_utils
from opentelemetry.trace import INVALID_SPAN_CONTEXT

from plan.common import utils
from plan.common.models import Exam, Lecture
from plan.common.snapshot import get_schedule_snapshot
from plan.ical import queue, views

FIXTURE_LECTURE_ID = 12

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def flush_ical_queue():
    queue.flush_for_tests()
    yield
    queue.flush_for_tests()


@pytest.fixture
def ical_url(schedule_url, schedule_scenario):
    def url(name, *args):
        return schedule_url(
            name,
            schedule_scenario.semester,
            schedule_scenario.student.slug,
            *args,
        )

    return url


def test_empty_ical(client, ical_url, cache_isolation):
    """This covers the semester not existing."""
    url = ical_url("schedule-ical")
    assert client.get(url).status_code == 404

    for arg in ("exams", "lectures"):
        url = ical_url("schedule-ical-type", arg)
        assert client.get(url.rstrip("/")).status_code == 301
        assert client.get(url).status_code == 404

    assert client.get(ical_url("schedule-ical-type", "foo")).status_code == 404


def test_ical(client, serialized_schedule_data, cache_isolation, frozen_time, ical_url):
    assert client.get(ical_url("schedule-ical")).status_code == 200

    for arg in ("exams", "lectures"):
        url = ical_url("schedule-ical-type", arg)
        assert client.get(url.rstrip("/")).status_code == 301
        assert client.get(url).status_code == 200

    url = ical_url("schedule-ical-type", "foo")
    assert client.get(url.rstrip("/")).status_code == 301
    assert client.get(url).status_code == 400


def test_ical_instruments_generation_phases(
    client, serialized_schedule_data, cache_isolation, frozen_time, ical_url
):
    with mock.patch.object(
        views.tracer, "start_as_current_span", return_value=nullcontext()
    ) as start_span:
        response = client.get(f"{ical_url('schedule-ical')}?no-cache=1")

    assert response.status_code == 200
    assert [call.args[0] for call in start_span.call_args_list] == [
        "ICAL LECTURES",
        "ICAL EXAMS",
        "ICAL SERIALIZE",
    ]


def test_ical_cache_writer_instruments_background_write():
    cache = mock.Mock()
    task = queue.QueuedCacheSet("disk", "test", "value", 60, INVALID_SPAN_CONTEXT)
    with (
        mock.patch.object(queue, "caches", {"disk": cache}),
        mock.patch.object(
            queue.tracer, "start_as_current_span", return_value=nullcontext()
        ) as start_span,
    ):
        queue._write_task(task)

    start_span.assert_called_once_with("ICAL CACHE WRITE", links=[])
    cache.set.assert_called_once_with("test", "value", timeout=60)


def test_ical_not_modified_returns_304_with_validator_headers(
    client,
    serialized_schedule_data,
    cache_isolation,
    frozen_time,
    ical_url,
    settings,
):
    settings.TIMETABLE_ENABLE_IF_MODIFIED_SINCE = True
    url = ical_url("schedule-ical")
    first = client.get(url)
    assert first.status_code == 200
    assert "Last-Modified" in first.headers

    second = client.get(url, HTTP_IF_MODIFIED_SINCE=first.headers["Last-Modified"])
    assert second.status_code == 304
    assert second.content == b""
    assert "Last-Modified" in second.headers
    assert "ETag" in second.headers


def test_ical_get_includes_etag_and_last_modified(
    client, serialized_schedule_data, cache_isolation, frozen_time, ical_url
):
    response = client.get(ical_url("schedule-ical"))
    assert response.status_code == 200
    assert "ETag" in response.headers
    assert "Last-Modified" in response.headers


def test_ical_if_none_match_matching_returns_304_with_no_body(
    client, serialized_schedule_data, cache_isolation, frozen_time, ical_url
):
    url = ical_url("schedule-ical")
    first = client.get(url)
    second = client.get(f"{url}?no-cache=1", HTTP_IF_NONE_MATCH=first.headers["ETag"])
    assert second.status_code == 304
    assert second.content == b""
    assert second.headers["ETag"] == first.headers["ETag"]
    assert "Last-Modified" in second.headers
    assert "X-Cache" not in second.headers


def test_ical_if_none_match_non_matching_returns_200(
    client, serialized_schedule_data, cache_isolation, frozen_time, ical_url
):
    response = client.get(ical_url("schedule-ical"), HTTP_IF_NONE_MATCH='"not-the-tag"')
    assert response.status_code == 200
    assert response.headers["ETag"] != '"not-the-tag"'


def test_ical_if_none_match_multiple_values_returns_304_on_match(
    client, serialized_schedule_data, cache_isolation, frozen_time, ical_url
):
    url = ical_url("schedule-ical")
    first = client.get(url)
    response = client.get(
        url, HTTP_IF_NONE_MATCH=f'"foo", {first.headers["ETag"]}, "bar"'
    )
    assert response.status_code == 304
    assert response.content == b""


def test_ical_if_none_match_wildcard_returns_304(
    client, serialized_schedule_data, cache_isolation, frozen_time, ical_url
):
    response = client.get(ical_url("schedule-ical"), HTTP_IF_NONE_MATCH="*")
    assert response.status_code == 304
    assert response.content == b""


def test_if_none_match_takes_precedence_over_if_modified_since(
    client, serialized_schedule_data, cache_isolation, frozen_time, ical_url
):
    url = ical_url("schedule-ical")
    first = client.get(url)
    response = client.get(
        url,
        HTTP_IF_NONE_MATCH='"does-not-match"',
        HTTP_IF_MODIFIED_SINCE=first.headers["Last-Modified"],
    )
    assert response.status_code == 200


def test_ical_head_matches_get_status_and_headers_with_no_body(
    client, serialized_schedule_data, cache_isolation, frozen_time, ical_url
):
    url = ical_url("schedule-ical")
    get_response = client.get(url)
    head_response = client.head(url)
    assert head_response.status_code == get_response.status_code
    assert head_response.headers["ETag"] == get_response.headers["ETag"]
    assert (
        head_response.headers["Last-Modified"] == get_response.headers["Last-Modified"]
    )
    assert head_response.content == b""

    conditional_head = client.head(url, HTTP_IF_NONE_MATCH=get_response.headers["ETag"])
    assert conditional_head.status_code == 304
    assert conditional_head.content == b""
    assert conditional_head.headers["ETag"] == get_response.headers["ETag"]


def test_ical_etag_is_stable_across_accept_encoding(
    client, serialized_schedule_data, cache_isolation, frozen_time, ical_url
):
    url = ical_url("schedule-ical")
    identity = client.get(url, HTTP_ACCEPT_ENCODING="")
    gzip = client.get(url, HTTP_ACCEPT_ENCODING="gzip")
    assert identity.status_code == 200
    assert gzip.status_code == 200
    assert identity.headers["ETag"] == gzip.headers["ETag"]


def test_ical_etag_is_hashed_not_raw(
    client,
    serialized_schedule_data,
    cache_isolation,
    frozen_time,
    schedule_scenario,
    ical_url,
):
    url = ical_url("schedule-ical")
    response = client.get(url, HTTP_ACCEPT_ENCODING="")
    etag = response.headers["ETag"]
    snapshot = get_schedule_snapshot(
        schedule_scenario.semester, schedule_scenario.student.slug
    )
    key = utils.response_cache_key("schedule-ical", snapshot.freshness_key(), url)
    assert etag.startswith('"') and etag.endswith('"')
    assert len(etag) == 66
    assert etag == utils.etag_for_key(key)


def test_ical_uses_last_modified_for_dtstamp(
    client, serialized_schedule_data, cache_isolation, frozen_time, ical_url
):
    response = client.get(f"{ical_url('schedule-ical')}?no-cache=1")
    assert response.status_code == 200
    assert "Last-Modified" in response.headers
    timestamp = http_utils.parse_http_date(response.headers["Last-Modified"])
    dtstamp = datetime.datetime.fromtimestamp(
        timestamp, tz=datetime.timezone.utc
    ).strftime("%Y%m%dT%H%M%SZ")
    assert f"DTSTAMP:{dtstamp}" in response.content.decode()


def test_ical_exam_event_timestamps_are_stable(
    client,
    serialized_schedule_data,
    cache_isolation,
    frozen_time,
    schedule_scenario,
    ical_url,
):
    response = client.get(
        f"{ical_url('schedule-ical-type', 'exams')}?no-cache=1",
        HTTP_ACCEPT_ENCODING="",
    )
    assert response.status_code == 200
    semester, student = schedule_scenario.semester, schedule_scenario.student
    exam = Exam.objects.get_exams(semester.year, semester.type, student.slug).filter(
        exam_time__isnull=False, handout_date__isnull=True
    )[0]
    expected_start = datetime.datetime.combine(
        exam.exam_date, exam.exam_time, tzinfo=views.TZ
    ).astimezone(datetime.timezone.utc)
    body = response.content.decode()
    event_start = body.index(f"UID:exam-{exam.id}@")
    event = body[event_start : body.index("END:VEVENT", event_start)]
    assert f"DTSTART:{expected_start.strftime('%Y%m%dT%H%M%SZ')}" in event


def test_ical_lecture_events_include_expected_summary_and_uid(
    client,
    serialized_schedule_data,
    cache_isolation,
    frozen_time,
    schedule_scenario,
    ical_url,
):
    snapshot = get_schedule_snapshot(
        schedule_scenario.semester, schedule_scenario.student.slug
    )
    response = client.get(
        f"{ical_url('schedule-ical-type', 'lectures')}?no-cache=1",
        HTTP_ACCEPT_ENCODING="",
    )
    assert response.status_code == 200
    lectures = Lecture.objects.get_lectures_data(
        snapshot.semester.id, snapshot.student.id
    )
    lecture = next(
        lecture for lecture in lectures if lecture.lecture_id == FIXTURE_LECTURE_ID
    )
    body = response.content.decode()
    uid_prefix = f"UID:lecture-{lecture.lecture_id}-"
    assert uid_prefix in body
    assert f"SUMMARY:{lecture.alias or lecture.course_code}" in body
    assert lecture.course_name in body
    if lecture.type_name:
        assert lecture.type_name in body
    event_start = body.index(uid_prefix)
    event = body[event_start : body.index("END:VEVENT", event_start)]
    if lecture.type_optional:
        assert "TRANSP:TRANSPARENT" in event


def test_ical_cache_ignores_encoding_variants(
    client, serialized_schedule_data, cache_isolation, frozen_time, ical_url
):
    url = ical_url("schedule-ical")
    br_first = client.get(url, HTTP_ACCEPT_ENCODING="br")
    queue.flush_for_tests()
    identity_first = client.get(url, HTTP_ACCEPT_ENCODING="")
    assert br_first.status_code == 200
    assert identity_first.status_code == 200
    assert "miss" in br_first.headers["X-Cache"]
    assert "hit" in identity_first.headers["X-Cache"]
    assert br_first.headers["ETag"] == identity_first.headers["ETag"]

    br_second = client.get(url, HTTP_ACCEPT_ENCODING="br")
    queue.flush_for_tests()
    identity_second = client.get(url, HTTP_ACCEPT_ENCODING="")
    gzip_first = client.get(url, HTTP_ACCEPT_ENCODING="gzip")
    gzip_second = client.get(url, HTTP_ACCEPT_ENCODING="gzip")
    assert "hit" in br_second.headers["X-Cache"]
    assert "hit" in identity_second.headers["X-Cache"]
    assert "hit" in gzip_first.headers["X-Cache"]
    assert "hit" in gzip_second.headers["X-Cache"]


def test_ical_cache_reuses_same_entry_across_encodings(
    client, serialized_schedule_data, cache_isolation, frozen_time, ical_url
):
    url = ical_url("schedule-ical")
    identity_first = client.get(url, HTTP_ACCEPT_ENCODING="")
    queue.flush_for_tests()
    assert identity_first.status_code == 200
    assert "miss" in identity_first.headers["X-Cache"]
    assert "hit" in client.get(url, HTTP_ACCEPT_ENCODING="br").headers["X-Cache"]
    assert "hit" in client.get(url, HTTP_ACCEPT_ENCODING="gzip").headers["X-Cache"]


def test_ical_type_without_trailing_slash_redirects_to_canonical_url(
    client, serialized_schedule_data, cache_isolation, frozen_time, ical_url
):
    url = ical_url("schedule-ical-type", "lectures")
    response = client.get(url.rstrip("/"), follow=False)
    assert response.status_code == 301
    assert response["Location"] == url
