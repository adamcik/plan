# This file is part of the plan timetable generator, see LICENSE for details.

from unittest import mock

from plan.common.models import Semester
from plan.common.tests import BaseTestCase
from plan.scrape.management.commands.scrape import Command


class DBTestCase(BaseTestCase):
    pass


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
