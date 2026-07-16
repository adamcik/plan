# This file is part of the plan timetable generator, see LICENSE for details.

from django.http import HttpResponse

from django.conf import settings
from django.core.cache import caches
import pytest

from plan.common.snapshot import semester_freshness_cache_key
from plan.common.utils import (
    ColorMap,
    clear_cache,
    compact_sequence,
    lookup_cached_response,
    store_cached_response,
)


pytestmark = pytest.mark.django_db


def test_colormap(serialized_schedule_data, cache_isolation, frozen_time):
    c = ColorMap()
    keys = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 3, 5, 6]
    for k in keys:
        assert c[k] == "color%d" % (k % c.max)

    c = ColorMap(hex=True)
    for k in keys:
        assert c[k] == settings.TIMETABLE_COLORS[k % c.max]

    assert c[None] == ""


def test_compact_sequence(serialized_schedule_data, cache_isolation, frozen_time):
    seq = compact_sequence([1, 2, 3, 5, 6, 7, 8, 12, 13, 15, 17, 19])
    assert seq == ["1-3", "5-8", "12-13", "15", "17", "19"]

    seq = compact_sequence([1, 2, 3])
    assert seq == ["1-3"]

    seq = compact_sequence([1, 3])
    assert seq == ["1", "3"]

    assert compact_sequence([]) == []


def test_response_cache_headers_include_the_cache_key(
    serialized_schedule_data, cache_isolation, frozen_time
):
    response = store_cached_response(
        cache_alias="default",
        cache_key="student-123",
        response=HttpResponse(),
        timeout=60,
    )

    assert response.headers["X-Cache"] == "miss; key=student-123"

    cached = lookup_cached_response(
        cache_alias="default",
        cache_key="student-123",
        headers={},
    )

    assert cached is not None
    assert cached.headers["X-Cache"] == "hit; key=student-123"


def test_clear_cache_deletes_only_user_schedule_entry(
    serialized_schedule_data, cache_isolation, frozen_time, schedule_scenario
):
    schedule = schedule_scenario.schedule
    freshness = schedule.freshness_key()

    dto_key = f"schedule:v2:{schedule.semester.year}-{schedule.semester.type}-{schedule.student.slug}"
    semester_key = semester_freshness_cache_key(schedule.semester)
    db_key = f"db:schedule:{freshness}"
    resp_key = f"resp:schedule:{freshness}:/"

    caches["default"].set(dto_key, "dto", timeout=60)
    caches["disk"].set(dto_key, "dto", timeout=60)
    caches["default"].set(semester_key, "semester", timeout=60)
    caches["default"].set(db_key, "db", timeout=60)
    caches["default"].set(resp_key, "resp", timeout=60)

    clear_cache(schedule)

    assert caches["default"].get(dto_key) is None
    assert caches["disk"].get(dto_key) is None
    assert caches["default"].get(semester_key) == "semester"
    assert caches["default"].get(db_key) == "db"
    assert caches["default"].get(resp_key) == "resp"


def test_store_cached_response_rejects_unsupported_queued_aliases(
    serialized_schedule_data, cache_isolation, frozen_time, settings
):
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "default-utils",
        },
        "disk": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "disk-utils",
        },
        "ical": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "ical-utils",
        },
    }

    with pytest.raises(ValueError, match="queued response caching"):
        store_cached_response(
            cache_alias="ical",
            cache_key="key",
            response=HttpResponse("ok"),
            timeout=60,
            queued=True,
        )
