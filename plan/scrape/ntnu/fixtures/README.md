# NTNU scraper fixtures

The schedule payloads in this directory were captured from NTNU's `schedules`
endpoint on 2026-08-23. They retain the source fields interpreted by the
scraper, while unrelated records and staff details have been removed.

Each filename records the course and semester used for the request. These are
parser fixtures, not complete snapshots of a course's timetable.

`bev1012_fall_2025_deadline.json` is different: it records two persisted
lectures found in production after the original NTNU response was no longer
available. The rows came from lecture IDs 417547 and 417548 and preserve the
midnight deadline case that motivated skipping unmappable timetable entries.
