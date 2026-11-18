import datetime

import pytest

from django.core.management import CommandError, call_command

from plan.common.models import Course, Lecture, Semester
from plan.scrape import capture, importing, snapshot
from plan.scrape.models import SnapshotImportRun
from plan.scrape.test_ntnu_capture import full_snapshot, install_source
from plan.scrape.test_snapshot_import import new_capture

pytestmark = pytest.mark.django_db


def test_pipeline_archives_raw_data_and_imports_exactly_this_run(monkeypatch, tmp_path):
    install_source(monkeypatch)
    call_command(
        "run_semester_snapshot",
        year=2026,
        type="spring",
        directory=tmp_path,
        import_snapshot=True,
        create=True,
    )
    assert len(list(tmp_path.glob("*/snapshot.json"))) == 1
    assert Course.objects.count() == Lecture.objects.count() == 1
    run = SnapshotImportRun.objects.get()
    assert run.status == "succeeded"
    assert run.finished_at >= run.started_at
    assert run.source_name == "ntnu"
    assert run.source_format_version == 1
    assert len(run.content_sha256) == 64
    assert run.diff["lectures"]["created"] == 1


def test_failed_capture_does_not_fall_back_to_an_earlier_archive(monkeypatch, tmp_path):
    install_source(monkeypatch)
    call_command("run_semester_snapshot", year=2026, type="spring", directory=tmp_path)
    install_source(monkeypatch, fail_schedule=True)
    with pytest.raises(CommandError, match="capture incomplete"):
        call_command(
            "run_semester_snapshot",
            year=2026,
            type="spring",
            directory=tmp_path,
            import_snapshot=True,
            create=True,
        )
    assert not Semester.objects.exists()
    assert not SnapshotImportRun.objects.exists()
    assert len(list(tmp_path.glob("*/snapshot.json"))) == 2


def test_normalization_failure_keeps_complete_raw_capture_and_audit(
    monkeypatch, tmp_path
):
    install_source(monkeypatch, malformed=True)
    with pytest.raises(CommandError, match="schedules array"):
        call_command(
            "run_semester_snapshot",
            year=2026,
            type="spring",
            directory=tmp_path,
            import_snapshot=True,
            create=True,
        )
    archived = capture.load_snapshot(next(tmp_path.glob("*/snapshot.json")))
    assert archived.results[-1].payload.data == {
        "unparsed": [True, None, {"future": "field"}]
    }
    assert archived.manifest.status == snapshot.RunStatus.COMPLETE
    assert "schedules array" in SnapshotImportRun.objects.get(status="failed").error
    assert not Semester.objects.exists()


def test_guard_rejection_is_audited_without_committing_changes(monkeypatch, tmp_path):
    importing.import_snapshot(
        full_snapshot(monkeypatch, tmp_path / "first"), create=True
    )
    newer = new_capture(monkeypatch, tmp_path / "newer", schedule={"schedules": []})
    with pytest.raises(importing.SnapshotImportError, match="deletion"):
        importing.import_snapshot(newer)
    assert "deletion" in SnapshotImportRun.objects.get(status="failed").error
    assert Lecture.objects.count() == 1


def test_old_run_cannot_undo_newer_import(monkeypatch, tmp_path):
    now = datetime.datetime(2026, 3, 2, tzinfo=datetime.UTC)
    monkeypatch.setattr(capture, "_utc_now", lambda: now)
    importing.import_snapshot(
        full_snapshot(monkeypatch, tmp_path / "newer"), create=True
    )
    now -= datetime.timedelta(days=1)
    older = full_snapshot(monkeypatch, tmp_path / "older")
    with pytest.raises(importing.SnapshotImportError, match="older"):
        importing.import_snapshot(older)


def test_accepted_id_cannot_be_reused_for_changed_payload(monkeypatch, tmp_path):
    archived = full_snapshot(monkeypatch, tmp_path)
    importing.import_snapshot(archived, create=True)
    archived.results[0].payload.data["courses"][0]["courseName"] = "Changed"
    with pytest.raises(importing.SnapshotImportError, match="different content"):
        importing.import_snapshot(archived)
    assert Course.objects.get().name == "TDT4100"


def test_completed_run_can_be_resumed_and_reimported_without_refetch(
    monkeypatch, tmp_path
):
    archived = full_snapshot(monkeypatch, tmp_path)
    importing.import_snapshot(archived, create=True)
    before = Semester.objects.get().version

    def no_network(*args, **kwargs):
        pytest.fail("completed run must not refetch")

    monkeypatch.setattr("plan.scrape.fetch.session.send", no_network)
    call_command(
        "capture_semester_snapshot",
        year=2026,
        type="spring",
        directory=tmp_path,
        resume=True,
    )
    importing.import_snapshot(capture.load_snapshot(tmp_path))
    assert Semester.objects.get().version == before
    assert SnapshotImportRun.objects.filter(status="succeeded").count() == 2


def test_dry_run_has_no_audit_or_operational_side_effects(monkeypatch, tmp_path):
    importing.import_snapshot(
        full_snapshot(monkeypatch, tmp_path), create=True, dry_run=True
    )
    assert not SnapshotImportRun.objects.exists()
    assert not Semester.objects.exists()
