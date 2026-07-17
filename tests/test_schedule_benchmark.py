"""Repeatable response-cache-miss baselines for schedule rendering."""

import re

from lxml import html
import pytest

from django.template.loader import get_template
from django.urls import reverse

from plan.common import timetable, views
from plan.common.models import Semester
from plan.common.snapshot import get_schedule_snapshot
from plan.common.table_render import render_schedule_table


def _semantic_tree(element):
    attributes = []
    for name, value in element.attrib.items():
        if name == "class":
            value = " ".join(sorted(value.split()))
        else:
            value = value.strip()
        attributes.append((name, value))
    text = re.sub(r"\s+", " ", element.text or " ").strip()
    return (
        element.tag,
        tuple(sorted(attributes)),
        text,
        tuple(_semantic_tree(child) for child in element),
    )


def _semantic_fragment(markup):
    return _semantic_tree(html.fragment_fromstring(markup, create_parent="fragment"))


def _assert_semantic_equal(actual, expected, path="fragment"):
    assert actual[:3] == expected[:3], path
    assert len(actual[3]) == len(expected[3]), path
    for index, (actual_child, expected_child) in enumerate(zip(actual[3], expected[3])):
        _assert_semantic_equal(actual_child, expected_child, f"{path}/{index}")


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


@pytest.mark.benchmark
def test_worst_case_schedule_table_template_baseline(
    benchmark, benchmark_schedule_data, cache_isolation
):
    """Measure only the existing schedule-table template hot loop."""
    table, rooms, snapshot = _schedule_table_context()
    template = get_template("schedule_table.html")
    context = {
        "next_week": None,
        "prev_week": None,
        "rooms": rooms,
        "schedule": snapshot,
        "timetable": table,
    }

    rendered = benchmark(template.render, context)

    assert 'id="schedule"' in rendered


def test_native_schedule_table_matches_template_semantics(
    benchmark_schedule_data, cache_isolation
):
    """Keep the native proof of concept aligned with the template it replaces."""
    table, rooms, snapshot = _schedule_table_context()
    context = {
        "next_week": 2,
        "prev_week": 1,
        "rooms": rooms,
        "schedule": snapshot,
        "timetable": table,
    }

    template_output = get_template("schedule_table.html").render(context)
    native_output = render_schedule_table(table, rooms, snapshot, 1, 2)

    _assert_semantic_equal(
        _semantic_fragment(native_output), _semantic_fragment(template_output)
    )


@pytest.mark.benchmark
def test_worst_case_native_schedule_table_baseline(
    benchmark, benchmark_schedule_data, cache_isolation
):
    """Measure the native schedule-table proof of concept against the template."""
    table, rooms, snapshot = _schedule_table_context()

    rendered = benchmark(render_schedule_table, table, rooms, snapshot, None, None)

    assert 'id="schedule"' in rendered
    assert "lecture-437341" in rendered
