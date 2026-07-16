import datetime

from django.core.cache import caches
from django.urls import reverse

from plan.common.models import Semester


def test_frozen_time_uses_legacy_reference_date(frozen_time):
    assert frozen_time == datetime.datetime(2009, 1, 1)


def test_cache_isolation_clears_timetable_caches(cache_isolation):
    assert caches["default"].get("fixture-test") is None
    assert caches["disk"].get("fixture-test") is None


def test_schedule_scenario_exposes_timetable_setup(schedule_scenario):
    assert schedule_scenario.semester.year == 2009
    assert schedule_scenario.student.slug == "adamcik"


def test_schedule_url_builds_default_and_explicit_urls(schedule_url):
    assert schedule_url("shortcut", "adamcik") == reverse("shortcut", args=["adamcik"])


def test_serialized_schedule_data_loads_timetable_fixtures(serialized_schedule_data):
    assert serialized_schedule_data["lecture_events"] == "test_lecture_events.json"
    assert Semester.objects.get(year=2009, type=Semester.SPRING).pk == 1
