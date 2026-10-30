import json
from pathlib import Path

import pytest

from plan.common.models import Course, Semester
from plan.scrape.ntnu.web import Lectures


pytestmark = pytest.mark.django_db

FIXTURE_DIR = Path(__file__).with_name("fixtures")


def scrape_fixture(monkeypatch, filename, course_code):
    with (FIXTURE_DIR / filename).open(encoding="utf-8") as fixture_file:
        payload = json.load(fixture_file)

    semester = Semester.objects.create(year=2026, type=Semester.SPRING)
    course = Course.objects.create(
        semester=semester,
        code=course_code,
        version="1",
        name=course_code,
        url=f"https://www.ntnu.no/studier/emner/{course_code}",
    )
    monkeypatch.setattr(Lectures, "course_queryset", lambda self: [course])
    monkeypatch.setattr(
        "plan.scrape.ntnu.web.fetch_course_lectures",
        lambda semester, course: payload,
    )

    return list(Lectures(semester).scrape())


def test_medicine_fixture_falls_back_to_discipline_groups(monkeypatch):
    lectures = scrape_fixture(
        monkeypatch, "mdt4043_spring_2026.json", course_code="MDT4043"
    )

    assert len(lectures) == 2
    assert {lecture["groups"] for lecture in lectures} == {
        ("Patologi og rettsmedisin",)
    }
    assert [lecture["weeks"] for lecture in lectures] == [{7}, {7}]


def test_tdt_fixture_groups_recurring_weeks(monkeypatch):
    lectures = scrape_fixture(
        monkeypatch, "tdt4100_spring_2026.json", course_code="TDT4100"
    )

    assert len(lectures) == 1
    assert lectures[0]["weeks"] == {12, 13}
    assert lectures[0]["title"] == "Forelesning 1"
    assert lectures[0]["summary"] is None
    assert {"BIT", "MTDT", "MTIØT"}.issubset(lectures[0]["groups"])


def test_exph_fixture_preserves_cross_campus_groups(monkeypatch):
    lectures = scrape_fixture(
        monkeypatch, "exph0300_spring_2026.json", course_code="EXPH0300"
    )

    assert len(lectures) == 1
    assert lectures[0]["weeks"] == {9, 10}
    assert lectures[0]["summary"] is None
    assert "EX.PHIL ÅLESUND" in lectures[0]["groups"]


def test_tma_fixture_covers_conventional_recurring_lecture(monkeypatch):
    lectures = scrape_fixture(
        monkeypatch, "tma4125_spring_2026.json", course_code="TMA4125"
    )

    assert len(lectures) == 1
    assert lectures[0]["weeks"] == {4, 5}
    assert lectures[0]["groups"] == ("MTGEORT", "MTINGGEO", "MTMT")
    assert lectures[0]["title"] == "Forelesning"
    assert lectures[0]["summary"] is None


def test_master_fixture_groups_both_weekly_slots(monkeypatch):
    lectures = scrape_fixture(
        monkeypatch, "aar4400_spring_2026.json", course_code="AAR4400"
    )

    assert len(lectures) == 2
    assert [lecture["weeks"] for lecture in lectures] == [{10, 11}, {10, 11}]
    assert {lecture["groups"] for lecture in lectures} == {("MAAR",)}
    assert all(not lecture["title"] for lecture in lectures)
    assert all(lecture["summary"] == "Lectures" for lecture in lectures)
