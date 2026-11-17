import pytest

from django.test import override_settings

from plan.common.models import Course, Exam, Lecture, Semester, Student, Subscription
from plan.scrape import capture, importing, records, snapshot
from plan.scrape.ntnu import capture as ntnu
from plan.scrape.test_capture import OpaqueCapture
from plan.scrape.test_ntnu_capture import (
    full_snapshot,
    install_source,
    source_course,
    source_schedule,
)

pytestmark = pytest.mark.django_db


def new_capture(monkeypatch, path, **source_options):
    install_source(monkeypatch, **source_options)
    semester = snapshot.Semester(year=2026, type="spring")
    capture.run_capture(ntnu.Capture(semester), semester, path)
    return capture.load_snapshot(path, require_complete=False)


def test_full_offline_normalization_import_and_replay(monkeypatch, tmp_path):
    archived = full_snapshot(monkeypatch, tmp_path)

    def no_network(*args, **kwargs):
        pytest.fail("replay must not acquire data")

    monkeypatch.setattr("plan.scrape.fetch.session.send", no_network)
    importing.import_snapshot(archived, create=True)
    semester = Semester.objects.get()
    lecture = Lecture.objects.get()
    assert list(lecture.weeks.values_list("number", flat=True)) == [12, 13]
    assert lecture.rooms.get().url.startswith("http")
    assert Exam.objects.get().exam_date.isoformat() == "2026-05-20"
    first_version = semester.version
    stats = importing.import_snapshot(archived)
    semester.refresh_from_db()
    assert semester.version == first_version
    assert Lecture.objects.get().pk == lecture.pk
    assert all(
        row["created"] == row["updated"] == row["deleted"] == 0
        for row in stats.values()
    )


def test_dry_run_rolls_back_every_operational_write(monkeypatch, tmp_path):
    stats = importing.import_snapshot(
        full_snapshot(monkeypatch, tmp_path), create=True, dry_run=True
    )
    assert stats["courses"]["created"] == stats["lectures"]["created"] == 1
    assert not Semester.objects.exists()
    assert not Course.objects.exists()
    assert not Lecture.objects.exists()


def test_large_deletion_rolls_back_course_changes(monkeypatch, tmp_path):
    importing.import_snapshot(
        full_snapshot(monkeypatch, tmp_path / "first"), create=True
    )
    changed_course = dict(source_course(), courseName="Must roll back")
    newer = new_capture(
        monkeypatch,
        tmp_path / "newer",
        course_rows=[changed_course],
        schedule={"schedules": []},
    )
    with pytest.raises(importing.SnapshotImportError, match="deletion of 1/1"):
        importing.import_snapshot(newer)
    assert Course.objects.get().name == "TDT4100"
    stats = importing.import_snapshot(newer, max_delete_percent=100)
    assert not Lecture.objects.exists()
    assert stats["lectures"]["final"] == 0


def test_user_exclusions_prevent_destructive_rematching(monkeypatch, tmp_path):
    importing.import_snapshot(
        full_snapshot(monkeypatch, tmp_path / "first"), create=True
    )
    subscription = Subscription.objects.create(
        student=Student.objects.create(slug="user"), course=Course.objects.get()
    )
    lecture = Lecture.objects.get()
    subscription.exclude.add(lecture)
    newer = new_capture(monkeypatch, tmp_path / "newer", schedule={"schedules": []})
    with pytest.raises(importing.SnapshotImportError, match="user exclusions"):
        importing.import_snapshot(newer, max_delete_percent=100)
    assert subscription.exclude.get().pk == lecture.pk


def test_selected_absent_course_and_its_events_are_retained(monkeypatch, tmp_path):
    importing.import_snapshot(
        full_snapshot(monkeypatch, tmp_path / "first"), create=True
    )
    subscription = Subscription.objects.create(
        student=Student.objects.create(slug="user"), course=Course.objects.get()
    )
    newer = new_capture(
        monkeypatch, tmp_path / "newer", course_rows=[source_course("NEW1001")]
    )
    importing.import_snapshot(newer)
    assert Course.objects.count() == 2
    assert Lecture.objects.filter(course=subscription.course).exists()
    assert Exam.objects.filter(course=subscription.course).exists()


@pytest.mark.parametrize(
    "source_options,match",
    [
        ({"malformed": True}, "schedules array"),
        ({"fail_schedule": True}, "not complete"),
        ({"course_rows": []}, "empty complete"),
    ],
)
def test_uninterpretable_or_incomplete_source_cannot_write(
    monkeypatch, tmp_path, source_options, match
):
    archived = new_capture(monkeypatch, tmp_path, **source_options)
    with pytest.raises(importing.SnapshotImportError, match=match):
        importing.import_snapshot(archived, create=True)
    assert not Semester.objects.exists()


def test_domain_validation_happens_only_during_offline_decode(monkeypatch, tmp_path):
    payload = source_schedule()
    payload["schedules"][0]["week"] = 0
    archived = new_capture(monkeypatch, tmp_path, schedule=payload)
    assert archived.manifest.status == snapshot.RunStatus.COMPLETE
    assert archived.results[-1].payload.data == payload
    with pytest.raises(importing.SnapshotImportError):
        importing.import_snapshot(archived, create=True)
    assert not Semester.objects.exists()


def test_complete_envelope_cannot_hide_missing_source_pages(monkeypatch, tmp_path):
    archived = full_snapshot(monkeypatch, tmp_path)
    archived.manifest.results.pop(1)
    (tmp_path / capture.MANIFEST_NAME).write_text(archived.manifest.model_dump_json())
    with pytest.raises(
        importing.SnapshotImportError, match="missing successful archived"
    ):
        importing.import_snapshot(capture.load_snapshot(tmp_path), create=True)
    assert not Semester.objects.exists()


def test_partial_job_selection_is_not_authoritative_for_import(monkeypatch, tmp_path):
    install_source(monkeypatch)
    semester = snapshot.Semester(year=2026, type="spring")
    capture.run_capture(ntnu.Capture(semester, jobs=["lectures"]), semester, tmp_path)
    with pytest.raises(importing.SnapshotImportError, match="requires courses"):
        importing.import_snapshot(capture.load_snapshot(tmp_path), create=True)
    assert not Semester.objects.exists()


class ExampleDecoder:
    def decode(self, archived):
        return records.SemesterRecords(
            semester=archived.manifest.semester,
            courses=[
                records.CourseRecord(
                    code=code.upper(), version=None, name=code, url="", locations=[]
                )
                for code in archived.results[0].payload.data
            ],
            lectures=[],
            examinations=[],
        )


@override_settings(
    TIMETABLE_SNAPSHOT_DECODERS={
        "opaque-example": "plan.scrape.test_snapshot_import.ExampleDecoder"
    }
)
def test_registered_decoder_supports_another_capture_format(tmp_path):
    semester = snapshot.Semester(year=2030, type="spring")
    capture.run_capture(OpaqueCapture(), semester, tmp_path)
    importing.import_snapshot(capture.load_snapshot(tmp_path), create=True)
    assert set(Course.objects.values_list("code", flat=True)) == {"A", "B"}
