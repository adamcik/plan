# This file is part of the plan timetable generator, see LICENSE for details.

import datetime
from contextlib import nullcontext
from http import HTTPStatus
from unittest import mock

import pytest

from plan.common.models import Course, Group, Lecture
from plan.pdf import views

pytestmark = pytest.mark.django_db


@pytest.fixture
def pdf_url(schedule_url, schedule_scenario):
    def url(name, *args):
        return schedule_url(
            name, schedule_scenario.semester, schedule_scenario.student.slug, *args
        )

    return url


def test_pdf(client, cache_isolation, frozen_time, pdf_url):
    for size in (None, "A4", "A5", "A6", "A9", "A7"):
        url = pdf_url("schedule-pdf-size", size) if size else pdf_url("schedule-pdf")

        response = client.get(url)
        if size == "A9":
            assert response.status_code == 404
            continue

        assert response.status_code == 200
        assert client.get(url).status_code == 200


def test_pdf_response_is_pdf_document(
    client, serialized_schedule_data, cache_isolation, frozen_time, pdf_url
):
    response = client.get(pdf_url("schedule-pdf"))

    assert response.status_code == 200
    assert response.headers["Content-Type"] == "application/pdf"
    assert response.content.startswith(b"%PDF-")


def test_pdf_instruments_generation_phases(
    client, serialized_schedule_data, cache_isolation, frozen_time, pdf_url
):
    with mock.patch.object(
        views.tracer,
        "start_as_current_span",
        return_value=nullcontext(),
    ) as start_span:
        response = client.get(pdf_url("schedule-pdf"))

    assert response.status_code == 200
    assert [call.args[0] for call in start_span.call_args_list] == [
        "PDF DATA",
        "PDF TIMETABLE BUILD",
        "PDF TITLE",
        "PDF WRITE",
    ]


def test_pdf_rejects_timetable_too_dense_to_render(
    client, serialized_schedule_data, cache_isolation, frozen_time, pdf_url
):
    course = Course.objects.get(pk=1)
    group = Group.objects.get(pk=1)
    lectures = Lecture.objects.bulk_create(
        [
            Lecture(
                course=course,
                day=0,
                start=datetime.time(8, 15),
                end=datetime.time(9),
            )
            for _ in range(40)
        ]
    )
    Lecture.groups.through.objects.bulk_create(
        [
            Lecture.groups.through(lecture_id=lecture.id, group_id=group.id)
            for lecture in lectures
        ]
    )

    response = client.get(pdf_url("schedule-pdf"))

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.headers["Content-Type"] == "text/html; charset=utf-8"
    assert "error.html" in [template.name for template in response.templates]
    assert (
        b"This timetable has too many simultaneous activities to export as PDF."
        in response.content
    )


def test_pdf_sets_etag_header(
    client, serialized_schedule_data, cache_isolation, frozen_time, pdf_url
):
    response = client.get(pdf_url("schedule-pdf"))

    assert response.status_code == 200
    assert "ETag" in response.headers


def test_pdf_if_none_match_returns_304(
    client, serialized_schedule_data, cache_isolation, frozen_time, pdf_url
):
    url = pdf_url("schedule-pdf")
    first = client.get(url)

    second = client.get(url, HTTP_IF_NONE_MATCH=first.headers["ETag"])

    assert second.status_code == 304
    assert second.content == b""


def test_pdf_if_none_match_takes_precedence_over_if_modified_since(
    client, serialized_schedule_data, cache_isolation, frozen_time, pdf_url
):
    url = pdf_url("schedule-pdf")
    first = client.get(url)

    response = client.get(
        url,
        HTTP_IF_NONE_MATCH='"does-not-match"',
        HTTP_IF_MODIFIED_SINCE=first.headers.get("Last-Modified", ""),
    )

    assert response.status_code == 200
