# This file is part of the plan timetable generator, see LICENSE for details.

import datetime
import time
import zoneinfo

import pytest
from django.core.cache import caches
from django.utils import timezone

from plan.common.models import Course, Room, Semester
from plan.common.snapshot import semester_freshness_cache_key
from plan.scrape.base import CourseScraper, LectureScraper, Scraper
from plan.scrape.management.commands.scrape import Command
from plan.scrape.ntnu.web import Courses, Lectures


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def isolate_cache(cache_isolation):
    yield


def scrape_options(**overrides):
    options = {
        "verbosity": 0,
        "disable_cache": False,
        "max_per_second": 5,
        "year": 2009,
        "type": Semester.SPRING,
        "create": False,
        "dry_run": False,
        "pdb": False,
        "prefix": None,
    }
    options.update(overrides)
    return options


def run_with_scraper(monkeypatch, outcome, **overrides):
    class FakeScraper:
        def __init__(self, semester, prefix):
            self.semester = semester
            self.prefix = prefix

        def run(self):
            if outcome == "noop":
                return False
            if outcome in {"changed", "delete-only"}:
                return True
            raise AssertionError(f"Unknown fake scrape outcome: {outcome}")

    command = Command()
    monkeypatch.setattr(command, "load_scraper", lambda label: FakeScraper)
    monkeypatch.setattr(
        "plan.scrape.management.commands.scrape.utils.prompt", lambda message: True
    )
    command.handle_label("fake", **scrape_options(**overrides))


def test_run_with_progress_wrapper_does_not_raise(serialized_schedule_data):
    semester = Semester.objects.get(year=2009, type=Semester.SPRING)

    class DummyScraper(Scraper):
        def queryset(self):
            return Course.objects.none()

        def scrape(self):
            return iter(())

    assert DummyScraper(semester).run() is False


def test_successful_scrape_commit_bumps_semester_freshness(
    serialized_schedule_data, monkeypatch
):
    semester = Semester.objects.get(year=2009, type=Semester.SPRING)
    semester.version = 0
    semester.last_modified = None
    semester.save(update_fields=["version", "last_modified"])

    run_with_scraper(monkeypatch, outcome="changed")

    semester.refresh_from_db()
    assert semester.version == 1
    assert semester.last_modified is not None


def test_bump_semester_freshness_invalidates_cache_after_commit(
    serialized_schedule_data, cache_isolation, django_capture_on_commit_callbacks
):
    semester = Semester.objects.get(year=2009, type=Semester.SPRING)
    key = semester_freshness_cache_key(semester)
    caches["default"].set(key, "stale", timeout=60)

    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        Command().bump_semester_freshness(semester)
        assert caches["default"].get(key) == "stale"

    assert len(callbacks) == 1
    callbacks[0]()
    assert caches["default"].get(key) is None


def test_delete_only_committed_scrape_bumps_semester_freshness(
    serialized_schedule_data, monkeypatch
):
    semester = Semester.objects.get(year=2009, type=Semester.SPRING)
    semester.version = 0
    semester.last_modified = None
    semester.save(update_fields=["version", "last_modified"])

    run_with_scraper(monkeypatch, outcome="delete-only")

    semester.refresh_from_db()
    assert semester.version == 1
    assert semester.last_modified is not None


def test_noop_scrape_does_not_bump_semester_freshness(
    serialized_schedule_data, monkeypatch
):
    semester = Semester.objects.get(year=2009, type=Semester.SPRING)
    semester.version = 0
    semester.last_modified = None
    semester.save(update_fields=["version", "last_modified"])

    run_with_scraper(monkeypatch, outcome="noop")

    semester.refresh_from_db()
    assert semester.version == 0
    assert semester.last_modified is None


def test_dry_run_scrape_does_not_bump_semester_freshness(
    serialized_schedule_data, monkeypatch
):
    semester = Semester.objects.get(year=2009, type=Semester.SPRING)
    semester.version = 0
    semester.last_modified = None
    semester.save(update_fields=["version", "last_modified"])

    run_with_scraper(monkeypatch, outcome="changed", dry_run=True)

    semester.refresh_from_db()
    assert semester.version == 0
    assert semester.last_modified is None


def test_save_handles_duplicate_course_in_same_import(serialized_schedule_data):
    semester = Semester.objects.get(year=2009, type=Semester.SPRING)
    scraper = CourseScraper(semester)
    scraper.import_time = timezone.now()
    kwargs = {
        "code": "MAST2009",
        "version": "1",
        "semester": semester,
        "defaults": {
            "name": "Test Course",
            "url": "https://example.invalid",
            "points": "7.5",
            "last_modified": timezone.now(),
        },
    }

    first_obj, first_created = scraper.save({}, kwargs)
    second_obj, second_created = scraper.save({}, kwargs)

    assert first_created is True
    assert second_created is False
    assert first_obj.pk == second_obj.pk
    assert (
        Course.objects.filter(code="MAST2009", semester=semester, version="1").count()
        == 1
    )


def test_scraper_uses_timezone_aware_timestamps(serialized_schedule_data):
    semester = Semester.objects.get(year=2009, type=Semester.SPRING)
    scraper = CourseScraper(semester)

    assert timezone.is_aware(scraper.import_time)
    prepared = scraper.prepare_save({"code": "TST1001", "version": "1"})
    assert timezone.is_aware(prepared["defaults"]["last_modified"])


def test_scraper_logs_source_data_when_processing_fails(
    serialized_schedule_data, caplog
):
    semester = Semester.objects.get(year=2009, type=Semester.SPRING)
    source = {"course": "TST1001", "activities": [{"rooms": [{"id": "A-101"}]}]}

    class FailingScraper(Scraper):
        def queryset(self):
            return Course.objects.none()

        def scrape(self):
            yield {"_source": source}

        def prepare_data(self, data):
            raise ValueError("invalid source data")

    with pytest.raises(ValueError, match="invalid source data"):
        FailingScraper(semester).run()

    record = next(
        record
        for record in caplog.records
        if record.message == "Failed to process scraped data"
    )
    assert record.scrape_source == source


def test_room_upgrades_uncoded_room_with_matching_name(serialized_schedule_data):
    semester = Semester.objects.get(year=2009, type=Semester.SPRING)
    legacy_room = Room.objects.create(name="Legacy room")

    room = LectureScraper(semester).room(
        code="A-101", name="Legacy room", url="https://example.invalid/rooms/A-101"
    )

    assert room.pk == legacy_room.pk
    assert room.code == "A-101"
    assert room.url == "https://example.invalid/rooms/A-101"


def test_scrape_merges_duplicate_code_and_version_locations(
    serialized_schedule_data, monkeypatch
):
    semester = Semester.objects.get(year=2009, type=Semester.SPRING)
    scraper = Courses(semester)
    duplicate_rows = [
        {
            "courseCode": "TST1001",
            "courseVersion": "1",
            "courseName": "Test Course",
            "courseUrl": "https://example.invalid/TST1001",
            "location": "Trondheim",
        },
        {
            "courseCode": "TST1001",
            "courseVersion": "1",
            "courseName": "Test Course",
            "courseUrl": "https://example.invalid/TST1001",
            "location": "Gjovik,Trondheim",
        },
    ]
    monkeypatch.setattr(
        "plan.scrape.ntnu.web.fetch_courses", lambda semester: duplicate_rows
    )

    emitted = list(scraper.scrape())

    assert len(emitted) == 1
    assert emitted[0]["code"] == "TST1001"
    assert emitted[0]["version"] == "1"
    assert emitted[0]["locations"] == ["Gjovik", "Trondheim"]


def test_lecture_timestamps_are_parsed_in_configured_timezone(
    serialized_schedule_data, monkeypatch
):
    semester = Semester.objects.get(year=2009, type=Semester.SPRING)
    course = Course.objects.filter(semester=semester).order_by("id").first()
    assert course is not None

    oslo = zoneinfo.ZoneInfo("Europe/Oslo")
    start_local = datetime.datetime(2009, 2, 2, 9, 15, tzinfo=oslo)
    end_local = datetime.datetime(2009, 2, 2, 10, 0, tzinfo=oslo)
    payload = {
        "schedules": [
            {
                "artermin": "2009_VÅR",
                "from": int(start_local.timestamp() * 1000),
                "to": int(end_local.timestamp() * 1000),
                "name": "Lecture",
                "acronym": "L",
                "title": "Test",
                "summary": "Summary",
                "studyProgramKeys": ["ABC"],
                "disiplin": [],
                "rooms": [],
                "staff": [],
                "week": 6,
            }
        ]
    }

    try:
        with monkeypatch.context() as patch:
            patch.setenv("TZ", "UTC")
            time.tzset()
            patch.setattr(Lectures, "course_queryset", lambda self: [course])
            patch.setattr(
                "plan.scrape.ntnu.web.fetch_course_lectures",
                lambda semester, course: payload,
            )
            emitted = list(Lectures(semester).scrape())
    finally:
        time.tzset()

    assert len(emitted) == 1
    assert emitted[0]["day"] == 0
    assert emitted[0]["start"] == start_local.time()
    assert emitted[0]["end"] == end_local.time()
