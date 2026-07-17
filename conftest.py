"""Pytest fixtures shared by the Django test suite."""

from __future__ import annotations

import datetime
import shutil
from collections.abc import Callable, Iterator
from dataclasses import dataclass

import pytest
from testing.postgresql import PostgresqlFactory

from django.conf import settings
from django.core.cache import caches
from django.core.management import call_command
from django.db import connections
from django.test.utils import setup_databases, teardown_databases
from django.urls import reverse

from plan.common import managers, models, views
from plan.common.models import Semester, Student
from plan.common.schedule import Schedule


@dataclass(frozen=True)
class ScheduleScenario:
    semester: Semester
    student: Student
    schedule: Schedule
    next_schedule: Schedule
    default_args: tuple[int, str, str]


@pytest.fixture(scope="session")
def django_db_setup(django_db_blocker):
    """Provision one temporary PostgreSQL server for the pytest session."""
    initdb = shutil.which("initdb")
    postgres = shutil.which("postgres")
    if initdb is None or postgres is None:
        raise RuntimeError("PostgreSQL binaries not found on PATH")

    postgresql = PostgresqlFactory(
        cache_initialized_db=True,
        initdb=initdb,
        postgres=postgres,
    )()
    dsn = postgresql.dsn()
    database_settings = {
        **settings.DATABASES["default"],
        "NAME": dsn["database"],
        "USER": dsn["user"],
        "PASSWORD": dsn.get("password", ""),
        "HOST": dsn["host"],
        "PORT": str(dsn["port"]),
    }
    settings.DATABASES["default"] = database_settings
    connections.databases["default"] = database_settings
    connection = connections["default"]
    connection.close()
    connection.settings_dict = database_settings

    database_config = None
    try:
        with django_db_blocker.unblock():
            database_config = setup_databases(verbosity=0, interactive=False)
        yield
    finally:
        if database_config is not None:
            with django_db_blocker.unblock():
                teardown_databases(database_config, verbosity=0)
        postgresql.stop()


@pytest.fixture
def cache_isolation() -> Iterator[None]:
    """Keep timetable cache state local to the requesting test."""
    caches["default"].clear()
    caches["disk"].clear()
    yield
    caches["default"].clear()
    caches["disk"].clear()


@pytest.fixture
def frozen_time(monkeypatch: pytest.MonkeyPatch) -> datetime.datetime:
    """Set timetable application clocks to the legacy test reference date."""
    now = datetime.datetime(2009, 1, 1)
    for module in (models, views, managers):
        monkeypatch.setattr(module, "now", lambda: now, raising=False)
        monkeypatch.setattr(module, "today", lambda: now.date(), raising=False)
    return now


@pytest.fixture
def schedule_scenario() -> ScheduleScenario:
    """Provide the shared semester, student, and schedule values for tests."""
    semester = Semester(year=2009, type=Semester.SPRING)
    student = Student(slug="adamcik")
    return ScheduleScenario(
        semester=semester,
        student=student,
        schedule=Schedule(semester=semester, student=student),
        next_schedule=Schedule(
            semester=Semester(year=2009, type=Semester.FALL), student=student
        ),
        default_args=(2009, Semester.SPRING, "adamcik"),
    )


@pytest.fixture
def schedule_url(
    schedule_scenario: ScheduleScenario,
) -> Callable[[str, *object], str]:
    """Build timetable URLs using the standard schedule arguments by default."""

    def url(name: str, *args: object) -> str:
        return reverse(name, args=args or schedule_scenario.default_args)

    return url


@pytest.fixture
def serialized_schedule_data(db) -> dict[str, str]:
    """Load the serialized timetable data used by existing timetable tests."""
    fixture_names = {
        "schedule": "test_data.json",
        "users": "test_user.json",
        "lecture_events": "test_lecture_events.json",
    }
    call_command("loaddata", *fixture_names.values(), verbosity=0)
    return fixture_names
