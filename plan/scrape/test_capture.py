import datetime
import fcntl
import gzip
import json
import os
import stat

import pytest

from django.core.management import CommandError, call_command
from django.test import override_settings

from plan.scrape import _archive, capture, snapshot


class OpaqueCapture:
    source = snapshot.Source(name="opaque-example", format_version=7)

    def __init__(self, semester=None, *, jobs=None, max_per_second=5):
        self.configuration = {"plan": "example"}
        self.calls = []
        self.fail_b = False
        self.interrupt = False

    def run(self, context):
        catalog = context.fetch(
            {"kind": "discovery", "parameters": {"page": 1}}, self._catalog
        )
        if self.interrupt:
            raise KeyboardInterrupt

        yield catalog

        for key in catalog.payload.data:
            yield context.fetch({"resource": key}, lambda key=key: self._resource(key))

    def _catalog(self):
        self.calls.append("catalog")
        return snapshot.Payload(
            data=["a", "b"], metadata={"custom": {"arbitrary": True}}
        )

    def _resource(self, key):
        self.calls.append(key)
        return snapshot.Payload(
            data={"arbitrary": [key, 42, False, None]},
            error="upstream failure" if self.fail_b and key == "b" else None,
        )


def _semester():
    return snapshot.Semester(year=2030, type="spring")


def test_capture_knows_nothing_about_the_payload(tmp_path):
    adapter = OpaqueCapture()
    manifest = capture.run_capture(adapter, _semester(), tmp_path)
    assert manifest.status == snapshot.RunStatus.COMPLETE
    archived = capture.load_snapshot(tmp_path)
    assert archived.results[0].payload.data == ["a", "b"]
    assert archived.results[0].payload.metadata == {"custom": {"arbitrary": True}}
    assert archived.results[1].payload.data == {"arbitrary": ["a", 42, False, None]}


def test_resume_replays_successes_for_discovery_and_retries_failures(tmp_path):
    adapter = OpaqueCapture()
    adapter.fail_b = True
    first = capture.run_capture(adapter, _semester(), tmp_path)
    previous = capture.load_snapshot(tmp_path, require_complete=False)
    assert first.status == snapshot.RunStatus.FAILED

    adapter.fail_b = False
    resumed = capture.run_capture(adapter, _semester(), tmp_path, resume=True)

    assert resumed.snapshot_id == first.snapshot_id
    assert resumed.started_at == first.started_at
    assert adapter.calls == ["catalog", "a", "b", "b"]
    current = capture.load_snapshot(tmp_path)
    assert current.results[0] == previous.results[0]
    assert current.results[1] == previous.results[1]
    assert list((tmp_path / "failures").glob("*.json.gz"))
    assert len(list((tmp_path / "attempts").glob("*.json"))) == 1


def test_response_is_durable_before_discovery_or_yield(tmp_path):
    adapter = OpaqueCapture()
    adapter.interrupt = True
    with pytest.raises(KeyboardInterrupt):
        capture.run_capture(adapter, _semester(), tmp_path)
    assert len(list((tmp_path / "responses").glob("*.json.gz"))) == 1
    adapter.interrupt = False
    capture.run_capture(adapter, _semester(), tmp_path, resume=True)
    assert adapter.calls == ["catalog", "a", "b"]


def test_completed_run_resume_is_immutable_but_new_runs_fetch_again(tmp_path):
    adapter = OpaqueCapture()
    first = capture.run_capture(adapter, _semester(), tmp_path / "one")
    before = (tmp_path / "one/snapshot.json").read_bytes()
    capture.run_capture(adapter, _semester(), tmp_path / "one", resume=True)
    assert adapter.calls == ["catalog", "a", "b"]
    assert (tmp_path / "one/snapshot.json").read_bytes() == before
    second = capture.run_capture(adapter, _semester(), tmp_path / "two")
    assert second.snapshot_id != first.snapshot_id
    assert adapter.calls == ["catalog", "a", "b", "catalog", "a", "b"]


def test_resume_rejects_stale_or_different_runs(monkeypatch, tmp_path):
    now = datetime.datetime(2030, 1, 1, tzinfo=datetime.UTC)
    monkeypatch.setattr(capture, "_utc_now", lambda: now)
    adapter = OpaqueCapture()
    capture.run_capture(adapter, _semester(), tmp_path)
    with pytest.raises(capture.CaptureError, match="must match"):
        capture.run_capture(
            adapter, snapshot.Semester(year=2031, type="spring"), tmp_path, resume=True
        )
    now += datetime.timedelta(hours=25)
    with pytest.raises(capture.CaptureError, match="too old"):
        capture.run_capture(adapter, _semester(), tmp_path, resume=True)
    assert adapter.calls == ["catalog", "a", "b"]


def test_corrupt_archived_success_is_not_silently_refetched(tmp_path):
    adapter = OpaqueCapture()
    manifest = capture.run_capture(adapter, _semester(), tmp_path)
    path = tmp_path / manifest.results[0].file
    data = json.loads(gzip.decompress(path.read_bytes()))
    data["payload"]["data"] = ["tampered"]
    path.write_bytes(gzip.compress(json.dumps(data).encode(), mtime=0))
    with pytest.raises(snapshot.SnapshotValidationError, match="checksum mismatch"):
        capture.run_capture(adapter, _semester(), tmp_path, resume=True)
    assert adapter.calls == ["catalog", "a", "b"]


def test_unknown_files_and_overlapping_runs_are_preserved(tmp_path):
    marker = tmp_path / "operator-data"
    marker.write_text("keep")
    with pytest.raises(capture.CaptureError, match="not empty"):
        capture.run_capture(OpaqueCapture(), _semester(), tmp_path)
    assert marker.read_text() == "keep"
    with (tmp_path / ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(capture.CaptureError, match="another capture"):
            capture.run_capture(OpaqueCapture(), _semester(), tmp_path)


@override_settings(
    TIMETABLE_CAPTURES={"custom": "plan.scrape.test_capture.OpaqueCapture"}
)
def test_command_loads_the_registered_capture_without_database_access(tmp_path):
    call_command(
        "capture_semester_snapshot",
        "custom",
        year=2030,
        type="spring",
        directory=tmp_path,
    )
    assert capture.load_snapshot(tmp_path).manifest.source == OpaqueCapture.source
    with pytest.raises(CommandError, match="not empty"):
        call_command(
            "capture_semester_snapshot",
            "custom",
            year=2030,
            type="spring",
            directory=tmp_path,
        )
    call_command(
        "capture_semester_snapshot",
        "custom",
        year=2030,
        type="spring",
        directory=tmp_path,
        resume=True,
    )


def test_atomic_write_preserves_existing_file_on_failure(monkeypatch, tmp_path):
    path = tmp_path / "generated.json"
    _archive._write_json(path, {"before": True})
    before = path.read_bytes()

    def fail(*args):
        raise OSError("disk failure")

    monkeypatch.setattr(_archive.os, "replace", fail)
    with pytest.raises(OSError, match="disk failure"):
        _archive._write_json(path, {"after": True})
    assert path.read_bytes() == before
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize(
    "change",
    [
        lambda data: data.update(schema_version=True),
        lambda data: data.update(extra="not allowed"),
        lambda data: data["source"].update(format_version="7"),
        lambda data: data["semester"].update(year="2030"),
        lambda data: data["results"][0].update(file="../outside.json"),
        lambda data: data.update(finished_at=None),
    ],
)
def test_envelope_is_strict_while_payload_remains_opaque(tmp_path, change):
    capture.run_capture(OpaqueCapture(), _semester(), tmp_path)
    path = tmp_path / capture.MANIFEST_NAME
    data = json.loads(path.read_text())
    change(data)
    path.write_text(json.dumps(data))
    with pytest.raises(snapshot.SnapshotValidationError):
        capture.load_snapshot(tmp_path)


def test_atomic_writer_cleans_up_when_its_body_raises(tmp_path):
    path = tmp_path / "generated.json"
    _archive._write_json(path, {"before": True})
    before = path.read_bytes()

    with (
        pytest.raises(RuntimeError, match="interrupted write"),
        _archive._atomic_writer(path) as stream,
    ):
        stream.write(b"partial")
        raise RuntimeError("interrupted write")

    assert path.read_bytes() == before
    assert list(tmp_path.iterdir()) == [path]


def test_plan_exception_finalizes_evidence_and_releases_lock(tmp_path):
    class ExplodingCapture(OpaqueCapture):
        def run(self, context):
            yield from super().run(context)
            raise RuntimeError("source plan failed")

    manifest = capture.run_capture(ExplodingCapture(), _semester(), tmp_path)
    assert manifest.status == snapshot.RunStatus.FAILED
    assert "source plan failed" in manifest.errors[0]

    resumed = OpaqueCapture()
    assert (
        capture.run_capture(resumed, _semester(), tmp_path, resume=True).status
        == snapshot.RunStatus.COMPLETE
    )
    assert resumed.calls == []


def test_loaded_snapshot_resolves_requests_without_storage_knowledge(tmp_path):
    capture.run_capture(OpaqueCapture(), _semester(), tmp_path)
    archived = capture.load_snapshot(tmp_path)
    request = dict(reversed(list(archived.results[0].request.items())))

    assert archived.result_for(request) is archived.results[0]
    assert archived.result_for({"unknown": True}) is None


def test_source_cannot_use_context_after_run_has_closed(tmp_path):
    class RetainingCapture(OpaqueCapture):
        def run(self, context):
            self.context = context
            yield from super().run(context)

    adapter = RetainingCapture()
    capture.run_capture(adapter, _semester(), tmp_path)

    with pytest.raises(capture.CaptureError, match="context is closed"):
        adapter.context.fetch(
            {"resource": "later"},
            lambda: pytest.fail("closed context must not acquire"),
        )


def test_responses_are_gzipped_but_manifests_remain_readable(tmp_path):
    manifest = capture.run_capture(OpaqueCapture(), _semester(), tmp_path)

    assert (
        json.loads((tmp_path / capture.MANIFEST_NAME).read_text())["status"]
        == "complete"
    )
    for stored in manifest.results:
        assert stored.file.endswith(".json.gz")
        encoded = (tmp_path / stored.file).read_bytes()
        assert encoded.startswith(b"\x1f\x8b")
        assert json.loads(gzip.decompress(encoded))["status"] == "success"

    assert capture.load_snapshot(tmp_path).results[0].payload.data == ["a", "b"]


def test_gzip_output_has_no_variable_timestamp_or_filename(tmp_path):
    data = {"unicode": "blå", "values": [False, None, 42]}
    first, second = tmp_path / "first.json.gz", tmp_path / "second.json.gz"
    _archive._write_json(first, data)
    _archive._write_json(second, data)

    assert first.read_bytes() == second.read_bytes()
    assert first.read_bytes()[4:8] == b"\0\0\0\0"
    assert json.loads(gzip.decompress(first.read_bytes())) == data


def _make_plain_legacy_run(directory):
    path = directory / capture.MANIFEST_NAME
    manifest = json.loads(path.read_text())
    for stored in manifest["results"]:
        compressed = directory / stored["file"]
        plain = compressed.with_suffix("")
        plain.write_bytes(gzip.decompress(compressed.read_bytes()))
        compressed.unlink()
        stored["file"] = plain.relative_to(directory).as_posix()

    path.write_text(json.dumps(manifest))


def test_completed_plain_run_reads_and_resumes_unchanged(tmp_path):
    adapter = OpaqueCapture()
    capture.run_capture(adapter, _semester(), tmp_path)
    _make_plain_legacy_run(tmp_path)
    path = tmp_path / capture.MANIFEST_NAME
    before = path.read_bytes()
    digest = capture.load_snapshot(tmp_path).content_digest

    capture.run_capture(adapter, _semester(), tmp_path, resume=True)

    assert adapter.calls == ["catalog", "a", "b"]
    assert path.read_bytes() == before
    assert capture.load_snapshot(tmp_path).content_digest == digest
    assert not list((tmp_path / "responses").glob("*.gz"))


def test_resuming_plain_run_reuses_successes_and_compresses_new_results(tmp_path):
    adapter = OpaqueCapture()
    adapter.fail_b = True
    capture.run_capture(adapter, _semester(), tmp_path)
    _make_plain_legacy_run(tmp_path)

    adapter.fail_b = False
    capture.run_capture(adapter, _semester(), tmp_path, resume=True)
    archived = capture.load_snapshot(tmp_path)

    assert adapter.calls == ["catalog", "a", "b", "b"]
    assert [stored.file.endswith(".gz") for stored in archived.manifest.results] == [
        False,
        False,
        True,
    ]
    assert archived.results[-1].payload.error is None


@pytest.mark.parametrize("invalid", [b"not gzip", b"\x1f\x8b\x08\x00"])
def test_corrupt_or_truncated_gzip_is_rejected_without_refetch(tmp_path, invalid):
    adapter = OpaqueCapture()
    manifest = capture.run_capture(adapter, _semester(), tmp_path)
    (tmp_path / manifest.results[0].file).write_bytes(invalid)

    with pytest.raises(
        snapshot.SnapshotValidationError, match="cannot read archived result"
    ):
        capture.run_capture(adapter, _semester(), tmp_path, resume=True)

    assert adapter.calls == ["catalog", "a", "b"]


@pytest.mark.parametrize("report", ["fetch", "failure"])
def test_unyielded_acquisition_failure_prevents_completion_and_can_retry(
    tmp_path, report
):
    class DroppedFailure(OpaqueCapture):
        fail = True

        def run(self, context):
            request = {"job": "discovery"}
            if self.fail:
                if report == "failure":
                    context.failure(request, "source unavailable")
                else:
                    context.fetch(
                        request,
                        lambda: snapshot.Payload(data=None, error="source unavailable"),
                    )

                return iter(())

            return iter(
                [
                    context.fetch(
                        request, lambda: snapshot.Payload(data={"recovered": True})
                    )
                ]
            )

    adapter = DroppedFailure()
    failed = capture.run_capture(adapter, _semester(), tmp_path)

    assert failed.status == snapshot.RunStatus.FAILED
    assert "source unavailable" in " ".join(failed.errors)
    assert list((tmp_path / "failures").glob("*.json.gz"))

    adapter.fail = False
    recovered = capture.run_capture(adapter, _semester(), tmp_path, resume=True)

    assert recovered.status == snapshot.RunStatus.COMPLETE
    assert capture.load_snapshot(tmp_path).results[0].payload.data == {
        "recovered": True
    }


@pytest.mark.parametrize(
    "initial,changed", [(1, True), (0, False), ({"nested": [1]}, {"nested": [True]})]
)
def test_resume_rejects_type_changes_in_json_configuration(tmp_path, initial, changed):
    adapter = OpaqueCapture()
    adapter.configuration = {"selection": initial}
    capture.run_capture(adapter, _semester(), tmp_path)
    before = (tmp_path / capture.MANIFEST_NAME).read_bytes()

    adapter.configuration = {"selection": changed}
    with pytest.raises(capture.CaptureError, match="configuration must match"):
        capture.run_capture(adapter, _semester(), tmp_path, resume=True)

    assert (tmp_path / capture.MANIFEST_NAME).read_bytes() == before
    assert adapter.calls == ["catalog", "a", "b"]


def test_atomic_publication_syncs_parent_after_replace(monkeypatch, tmp_path):
    events = []
    sync, replace = os.fsync, os.replace

    def synced(fd):
        events.append(
            "directory sync" if stat.S_ISDIR(os.fstat(fd).st_mode) else "file sync"
        )
        sync(fd)

    def replaced(source, destination):
        replace(source, destination)
        events.append("replace")

    monkeypatch.setattr(_archive.os, "fsync", synced)
    monkeypatch.setattr(_archive.os, "replace", replaced)
    _archive._write_json(tmp_path / "record.json", {"data": True})

    publication = events.index("replace")
    assert "file sync" in events[:publication]
    assert "directory sync" in events[publication + 1 :]


def test_new_archive_directories_and_parent_entries_are_synced(monkeypatch, tmp_path):
    synced_directories = set()
    sync = os.fsync

    def synced(fd):
        info = os.fstat(fd)
        if stat.S_ISDIR(info.st_mode):
            synced_directories.add((info.st_dev, info.st_ino))

        sync(fd)

    monkeypatch.setattr(_archive.os, "fsync", synced)
    directory = tmp_path / "new" / "run"
    adapter = OpaqueCapture()
    adapter.fail_b = True
    capture.run_capture(adapter, _semester(), directory)

    adapter.fail_b = False
    capture.run_capture(adapter, _semester(), directory, resume=True)

    expected = {
        tmp_path,
        tmp_path / "new",
        directory,
        directory / "responses",
        directory / "failures",
        directory / "attempts",
    }
    assert {
        (path.stat().st_dev, path.stat().st_ino) for path in expected
    } <= synced_directories
