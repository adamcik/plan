# This file is part of the plan timetable generator, see LICENSE for details.

from unittest import mock
import datetime
import os
import time
import zoneinfo

from django.utils import timezone

from plan.common.models import Course
from plan.common.models import Semester
from plan.common.tests import BaseTestCase
from plan.scrape.base import CourseScraper
from plan.scrape.base import Scraper
from plan.scrape.management.commands.scrape import Command
from plan.scrape.ntnu.web import Courses
from plan.scrape.ntnu.web import Lectures


class DBTestCase(BaseTestCase):
    pass


class ScraperRunTestCase(BaseTestCase):
    fixtures = ["test_data.json", "test_user.json"]

    def test_run_with_progress_wrapper_does_not_raise(self):
        semester = Semester.objects.get(year=2009, type=Semester.SPRING)

        class DummyScraper(Scraper):
            def queryset(self):
                return Course.objects.none()

            def scrape(self):
                return iter(())

        scraper = DummyScraper(semester)
        needs_commit = scraper.run()

        self.assertFalse(needs_commit)


class StudwebTestCase(BaseTestCase):
    pass


class ManagmentTestCase(BaseTestCase):
    fixtures = ["test_data.json", "test_user.json"]

    def _options(self, **overrides):
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

    def _run_with_scraper(self, outcome, **overrides):
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
        with mock.patch.object(command, "load_scraper", return_value=FakeScraper):
            with mock.patch(
                "plan.scrape.management.commands.scrape.utils.prompt", return_value=True
            ):
                command.handle_label("fake", **self._options(**overrides))

    def test_successful_scrape_commit_bumps_semester_freshness(self):
        semester = Semester.objects.get(year=2009, type=Semester.SPRING)
        semester.version = 0
        semester.last_modified = None
        semester.save(update_fields=["version", "last_modified"])

        self._run_with_scraper(outcome="changed")

        semester.refresh_from_db()
        self.assertEqual(1, semester.version)
        self.assertIsNotNone(semester.last_modified)

    def test_delete_only_committed_scrape_bumps_semester_freshness(self):
        semester = Semester.objects.get(year=2009, type=Semester.SPRING)
        semester.version = 0
        semester.last_modified = None
        semester.save(update_fields=["version", "last_modified"])

        self._run_with_scraper(outcome="delete-only")

        semester.refresh_from_db()
        self.assertEqual(1, semester.version)
        self.assertIsNotNone(semester.last_modified)

    def test_noop_scrape_does_not_bump_semester_freshness(self):
        semester = Semester.objects.get(year=2009, type=Semester.SPRING)
        semester.version = 0
        semester.last_modified = None
        semester.save(update_fields=["version", "last_modified"])

        self._run_with_scraper(outcome="noop")

        semester.refresh_from_db()
        self.assertEqual(0, semester.version)
        self.assertIsNone(semester.last_modified)

    def test_dry_run_scrape_does_not_bump_semester_freshness(self):
        semester = Semester.objects.get(year=2009, type=Semester.SPRING)
        semester.version = 0
        semester.last_modified = None
        semester.save(update_fields=["version", "last_modified"])

        self._run_with_scraper(outcome="changed", dry_run=True)

        semester.refresh_from_db()
        self.assertEqual(0, semester.version)
        self.assertIsNone(semester.last_modified)


class CourseScraperTestCase(BaseTestCase):
    fixtures = ["test_data.json", "test_user.json"]

    def test_save_handles_duplicate_course_in_same_import(self):
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

        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(first_obj.pk, second_obj.pk)
        self.assertEqual(
            1,
            Course.objects.filter(
                code="MAST2009", semester=semester, version="1"
            ).count(),
        )

    def test_scraper_uses_timezone_aware_timestamps(self):
        semester = Semester.objects.get(year=2009, type=Semester.SPRING)
        scraper = CourseScraper(semester)

        self.assertTrue(timezone.is_aware(scraper.import_time))

        prepared = scraper.prepare_save({"code": "TST1001", "version": "1"})
        self.assertTrue(timezone.is_aware(prepared["defaults"]["last_modified"]))


class CoursesInputMergeTestCase(BaseTestCase):
    fixtures = ["test_data.json", "test_user.json"]

    def test_scrape_merges_duplicate_code_and_version_locations(self):
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

        with mock.patch(
            "plan.scrape.ntnu.web.fetch_courses", return_value=duplicate_rows
        ):
            emitted = list(scraper.scrape())

        self.assertEqual(1, len(emitted))
        self.assertEqual("TST1001", emitted[0]["code"])
        self.assertEqual("1", emitted[0]["version"])
        self.assertEqual(["Gjovik", "Trondheim"], emitted[0]["locations"])


class LecturesTimezoneParsingTestCase(BaseTestCase):
    fixtures = ["test_data.json", "test_user.json"]

    def test_lecture_timestamps_are_parsed_in_configured_timezone(self):
        semester = Semester.objects.get(year=2009, type=Semester.SPRING)
        course = Course.objects.filter(semester=semester).order_by("id").first()
        self.assertIsNotNone(course)

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

        old_tz = os.environ.get("TZ")
        try:
            os.environ["TZ"] = "UTC"
            time.tzset()

            scraper = Lectures(semester)
            with mock.patch.object(
                Lectures,
                "course_queryset",
                return_value=[course],
            ):
                with mock.patch(
                    "plan.scrape.ntnu.web.fetch_course_lectures",
                    return_value=payload,
                ):
                    emitted = list(scraper.scrape())
        finally:
            if old_tz is None:
                del os.environ["TZ"]
            else:
                os.environ["TZ"] = old_tz
            time.tzset()

        self.assertEqual(1, len(emitted))
        self.assertEqual(0, emitted[0]["day"])
        self.assertEqual(start_local.time(), emitted[0]["start"])
        self.assertEqual(end_local.time(), emitted[0]["end"])
