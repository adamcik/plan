"""Offline reconciliation with one transaction and explicit deletion limits.

Lecture matching deliberately uses the existing recurring-lecture heuristic,
not unproven NTNU activity identities. If matching would remove a lecture with
user exclusions, reject the entire import instead of losing that preference.
"""

import copy
import datetime
import logging
import math

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.module_loading import import_string

from plan.common.models import Course, Semester
from plan.scrape import base, records, snapshot, utils
from plan.scrape.management.commands.scrape import Command as ScrapeCommand
from plan.scrape.models import SnapshotImportRun


class SnapshotImportError(ValueError):
    pass


def import_snapshot(
    artifact: snapshot.Snapshot, *, create=False, dry_run=False, max_delete_percent=10
):
    manifest = artifact.manifest
    content_hash = artifact.content_digest
    run = None
    if not dry_run:
        run = SnapshotImportRun.objects.create(
            snapshot_id=manifest.snapshot_id,
            content_sha256=content_hash,
            source_name=manifest.source.name,
            source_format_version=manifest.source.format_version,
            year=manifest.semester.year,
            type=manifest.semester.type,
            schema_version=manifest.schema_version,
            captured_at=manifest.started_at,
            status="running",
        )

    try:
        return _import_snapshot(
            artifact,
            create=create,
            dry_run=dry_run,
            max_delete_percent=max_delete_percent,
            run=run,
            content_hash=content_hash,
        )
    except Exception as error:
        if run is not None:
            SnapshotImportRun.objects.filter(pk=run.pk).update(
                status="failed", error=str(error), finished_at=timezone.now()
            )

        raise


def _import_snapshot(
    artifact, *, create, dry_run, max_delete_percent, run, content_hash
):
    if not math.isfinite(max_delete_percent) or not 0 <= max_delete_percent <= 100:
        raise SnapshotImportError("max-delete-percent must be between 0 and 100")

    decoded = _decode_snapshot(artifact)
    data = decoded.model_dump(mode="json")
    sections = {
        name: {"status": "complete", "records": data[name]}
        for name in ("courses", "lectures", "examinations")
    }

    with transaction.atomic():
        semester_data = decoded.semester.model_dump()
        if create:
            Semester.objects.get_or_create(**semester_data)

        try:
            semester = Semester.objects.select_for_update().get(**semester_data)
        except Semester.DoesNotExist as error:
            raise SnapshotImportError(
                "semester does not exist; pass --create"
            ) from error

        previous = SnapshotImportRun.objects.filter(**semester_data, status="succeeded")
        latest = previous.order_by("-captured_at").first()
        if latest is not None and artifact.manifest.started_at < latest.captured_at:
            raise SnapshotImportError(
                "snapshot is older than the latest successful import"
            )

        if (
            SnapshotImportRun.objects.filter(
                snapshot_id=artifact.manifest.snapshot_id, status="succeeded"
            )
            .exclude(content_sha256=content_hash)
            .exists()
        ):
            raise SnapshotImportError(
                "snapshot ID was already imported with different content"
            )

        importers = [_Courses(semester, sections["courses"], max_delete_percent)]
        changed = importers[0].run()

        course_ids = [
            Course.objects.get(
                semester=semester, code=record["code"], version=record["version"]
            ).pk
            for record in sections["courses"]["records"]
        ]
        importers.extend(
            [
                _Lectures(
                    semester, sections["lectures"], max_delete_percent, course_ids
                ),
                _Examinations(
                    semester, sections["examinations"], max_delete_percent, course_ids
                ),
            ]
        )
        for importer in importers[1:]:
            changed = importer.run() or changed

        if changed and not dry_run:
            ScrapeCommand().bump_semester_freshness(semester)

        if dry_run:
            transaction.set_rollback(True)

        stats = {
            type(importer).__name__.lstrip("_").lower(): dict(importer.stats)
            for importer in importers
        }

        if run is not None:
            SnapshotImportRun.objects.filter(pk=run.pk).update(
                status="succeeded", diff=stats, finished_at=timezone.now()
            )

        return stats


def _decode_snapshot(artifact: snapshot.Snapshot) -> records.SemesterRecords:
    if artifact.manifest.status != snapshot.RunStatus.COMPLETE:
        raise SnapshotImportError("snapshot acquisition is not complete")

    registry = getattr(settings, "TIMETABLE_SNAPSHOT_DECODERS", {})
    name = artifact.manifest.source.name
    if name not in registry:
        raise SnapshotImportError(f"no offline decoder registered for source: {name}")

    try:
        decoded = import_string(registry[name])().decode(artifact)
        if (
            not isinstance(decoded, records.SemesterRecords)
            or decoded.semester != artifact.manifest.semester
        ):
            raise ValueError("decoder returned records for a different semester")

        return decoded
    except (ValueError, TypeError, KeyError, ImportError, AttributeError) as error:
        raise SnapshotImportError(f"cannot decode source snapshot: {error}") from error


class _GuardedImport:
    def __init__(self, semester, section, max_delete_percent):
        super().__init__(semester)
        self.section = section
        self.max_delete_percent = max_delete_percent

    def log_stats(self):
        # Deletes have already run; the legacy summary subtracts them twice.
        self.stats["final"] = self.queryset().count()
        logging.getLogger(__name__).info("Snapshot import diff: %s", self.stats)

    def delete(self, queryset):
        count = queryset.count()
        initial = self.stats["initial"]
        if count and (not initial or count * 100 > initial * self.max_delete_percent):
            raise SnapshotImportError(
                f"{type(self).__name__.lstrip('_')}: deletion of {count}/{initial} exceeds max-delete-percent={self.max_delete_percent}"
            )

        self.log_delete(queryset)
        queryset.delete()

    def prepare_delete(self):
        if self.section["status"] != "complete":
            return self.queryset().none()

        return super().prepare_delete()


class _Courses(_GuardedImport, base.CourseScraper):
    extra_fields = (*base.CourseScraper.extra_fields, "syllabus")

    def scrape(self):
        for record in copy.deepcopy(self.section["records"]):
            if record.get("syllabus") is None:
                record.pop("syllabus", None)
            yield record

    def prepare_delete(self):
        return super().prepare_delete().filter(subscription__isnull=True)


class _CourseRelatedImport(_GuardedImport):
    def __init__(self, semester, section, max_delete_percent, course_ids):
        super().__init__(semester, section, max_delete_percent)
        self.course_ids = course_ids

    def queryset(self):
        # Retained selected courses absent from the source are outside the
        # authoritative import scope, including their lectures and examinations.
        queryset = super().queryset()
        return queryset.filter(course_id__in=self.course_ids)

    def scrape(self):
        for record in copy.deepcopy(self.section["records"]):
            reference = record.pop("course")
            course = Course.objects.get(semester=self.semester, **reference)
            record["course"] = course
            yield self.convert(record)

    def convert(self, record):
        return record


class _Lectures(_CourseRelatedImport, base.LectureScraper):
    def convert(self, record):
        record["start"] = datetime.time.fromisoformat(record["start"])
        record["end"] = datetime.time.fromisoformat(record["end"])
        return record

    def room(self, code, name, url):
        room = super().room(code, name, url)
        # The legacy helper omits URLs on creation. Set it in the same run so
        # replay is idempotent rather than requiring a second import to converge.
        if utils.valid_url(url) and room.url != url:
            self.update_room(room, {"url": url})

        return room

    def delete(self, queryset):
        if queryset.filter(excluded_from__isnull=False).exists():
            raise SnapshotImportError(
                "import would delete a lecture with user exclusions"
            )

        super().delete(queryset)


class _Examinations(_CourseRelatedImport, base.ExamScraper):
    def convert(self, record):
        record["exam_date"] = datetime.date.fromisoformat(record.pop("date"))
        return record
