"""Repeatable response-cache-miss baselines for schedule rendering."""

from dataclasses import replace

import pytest

from django.urls import reverse

from plan.common import timetable, views
from plan.common.models import Semester
from plan.common.snapshot import get_schedule_snapshot
from plan.common.table_render import render_lectures_table, render_schedule_table


def _schedule_table_context():
    semester = Semester.objects.get(year=2026, type=Semester.SPRING)
    snapshot = get_schedule_snapshot(semester, "debug")
    lectures, _, _, _, _, rooms, _, _ = views._schedule_data(snapshot)
    table = timetable.Timetable(lectures)
    table.place_lectures(None)
    table.do_expansion()
    table.insert_times()
    table.add_markers()
    return table, rooms, snapshot


def _lectures_context():
    semester = Semester.objects.get(year=2026, type=Semester.SPRING)
    snapshot = get_schedule_snapshot(semester, "debug")
    lectures, _, _, _, groups, rooms, _, _ = views._schedule_data(snapshot)
    lectures.sort(
        key=lambda lecture: (
            lecture.course_code,
            min(lecture.week_numbers) if lecture.week_numbers else None,
        )
    )
    return lectures, groups, rooms, snapshot


@pytest.mark.benchmark
def test_worst_case_schedule_rendering_baseline(
    benchmark, client, benchmark_schedule_data, cache_isolation
):
    """Measure construction and rendering after schedule data has been cached."""
    semester = Semester.objects.get(year=2026, type=Semester.SPRING)
    url = reverse("schedule", args=[semester, "debug"])

    warm_response = client.get(url, HTTP_CACHE_CONTROL="no-cache")
    assert warm_response.status_code == 200

    response = benchmark(lambda: client.get(url, HTTP_CACHE_CONTROL="no-cache"))

    assert response.status_code == 200


def test_non_template_schedule_table_escapes_dynamic_values(
    benchmark_schedule_data, cache_isolation
):
    table, rooms, snapshot = _schedule_table_context()
    hostile = '<script>alert("x")</script>'
    for timetable_row in table.table:
        for cell_group in timetable_row:
            for timetable_cell in cell_group:
                lecture = timetable_cell.get("lecture")
                if lecture:
                    timetable_cell["lecture"] = replace(
                        lecture,
                        alias=hostile,
                        course_name=hostile,
                        title=hostile,
                        stream='https://example.test/?q="<script>',
                    )

    rendered = render_schedule_table(table, rooms, snapshot, None, None)

    assert hostile not in rendered
    assert "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;" in rendered
    assert "&quot;&lt;script&gt;" in rendered


def test_non_template_lectures_table_escapes_dynamic_values(
    benchmark_schedule_data, cache_isolation
):
    lectures, groups, rooms, snapshot = _lectures_context()
    hostile = '<script>alert("x")</script>'
    lectures[0] = replace(
        lectures[0],
        alias=hostile,
        course_name=hostile,
        title=hostile,
        summary=hostile,
        type_name=hostile,
    )
    rooms[lectures[0].lecture_id] = [
        {**rooms[lectures[0].lecture_id][0], "name": hostile}
    ]
    groups[lectures[0].lecture_id] = [hostile]

    rendered = render_lectures_table(
        lectures, groups, rooms, snapshot, True, tabindex=30
    )

    assert hostile not in rendered
    assert "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;" in rendered


@pytest.mark.benchmark
def test_worst_case_non_template_schedule_table(
    benchmark, benchmark_schedule_data, cache_isolation
):
    """Measure non-template schedule-table rendering in isolation."""
    table, rooms, snapshot = _schedule_table_context()

    rendered = benchmark(render_schedule_table, table, rooms, snapshot, None, None)

    assert 'id="schedule"' in rendered
    assert "lecture-437341" in rendered


@pytest.mark.benchmark
def test_worst_case_non_template_lectures_table(
    benchmark, benchmark_schedule_data, cache_isolation
):
    """Measure non-template lecture-list rendering in isolation."""
    lectures, groups, rooms, snapshot = _lectures_context()

    rendered = benchmark(
        render_lectures_table, lectures, groups, rooms, snapshot, False, 30
    )

    assert 'id="lectures"' in rendered
