import fcntl

import pytest
from django.core.management import CommandError, call_command

from plan.scrape import capture
from plan.scrape.test_ntnu_capture import install_source


def test_recurring_capture_starts_fresh_runs(monkeypatch, tmp_path):
    calls = install_source(monkeypatch)
    for _ in range(2):
        call_command(
            "run_semester_snapshot", year=2026, type="spring", directory=tmp_path
        )
    paths = list(tmp_path.glob("*/snapshot.json"))
    assert len(paths) == 2
    assert (
        len({capture.load_snapshot(path).manifest.snapshot_id for path in paths}) == 2
    )
    assert len(calls) == 6


def test_failed_run_keeps_previous_success(monkeypatch, tmp_path):
    install_source(monkeypatch)
    call_command("run_semester_snapshot", year=2026, type="spring", directory=tmp_path)
    previous = next(tmp_path.glob("*/snapshot.json"))
    before = previous.read_bytes()
    install_source(monkeypatch, fail_schedule=True)
    with pytest.raises(CommandError, match="capture incomplete"):
        call_command(
            "run_semester_snapshot", year=2026, type="spring", directory=tmp_path
        )
    assert previous.read_bytes() == before
    assert len(list(tmp_path.glob("*/snapshot.json"))) == 2


def test_overlapping_runs_are_rejected(tmp_path):
    with (tmp_path / ".capture.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(CommandError, match="another snapshot run"):
            call_command(
                "run_semester_snapshot", year=2026, type="spring", directory=tmp_path
            )
    assert not list(tmp_path.glob("*/snapshot.json"))
