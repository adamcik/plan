# 04 — Convert timetable domain tests to pytest

**What to build:** Timetable model, manager, converter, utility, command, and scheduling behavior is covered through explicit pytest fixtures rather than inherited test setup.

**Blocked by:** 03 — Publish schedule test fixtures.

**Status:** resolved

- [x] Timetable domain behavior runs as module-level pytest functions with explicit database and scenario dependencies.
- [x] Assertions describe observable outcomes using pytest conventions.
- [x] Existing serialized timetable scenarios continue to verify the same behavior.

## Comments

Resolved by converting timetable domain, manager, converter, utility, command, and scheduling tests to explicit pytest fixtures and assertions.
