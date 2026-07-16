# 03 — Publish schedule test fixtures

**What to build:** Database-backed timetable tests can explicitly request typed schedule scenarios, frozen application time, cache isolation, URL helpers, and the existing serialized timetable data without inherited setup.

**Blocked by:** 01 — Establish pytest PostgreSQL test platform.

**Status:** resolved

- [x] A typed schedule scenario exposes the shared semester, student, and schedule data required by timetable tests.
- [x] Time, cache, URL, and serialized-data setup are independently requestable fixtures.
- [x] The fixtures preserve the currently tested timetable behavior while making database access explicit.

## Comments

Resolved with shared pytest fixtures in `conftest.py` and fixture-consumption coverage in `tests/test_schedule_fixtures.py`.
