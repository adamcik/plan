"""Public acquisition seam: a source-owned plan and a durable request context.

Adapters describe requests and acquire opaque payloads. The context owns replay
and persistence before discovery continues. Archive lifetimes and file formats
remain internal; an offline decoder receives a verified Snapshot instead.
"""

import datetime
from collections.abc import Callable, Iterator
from typing import Protocol

import pydantic

from plan.scrape import _archive, snapshot
from plan.scrape._archive import MANIFEST_NAME, load_snapshot
from plan.scrape._archive import ArchiveError as CaptureError

__all__ = [
    "MANIFEST_NAME",
    "Adapter",
    "CaptureError",
    "Context",
    "load_snapshot",
    "run_capture",
]


class Context(Protocol):
    """Run-scoped acquisition, valid only while the adapter's plan executes.

    Request metadata must identify all inputs affecting the response. Fetch
    returns the persisted success or failure, including the payload needed for
    discovery. Only this run's successful requests are replayed.
    """

    def fetch(
        self,
        request: dict[str, pydantic.JsonValue],
        loader: Callable[[], snapshot.Payload],
    ) -> snapshot.CaptureResult: ...

    def failure(
        self, request: dict[str, pydantic.JsonValue], error: str
    ) -> snapshot.CaptureResult: ...


class Adapter(Protocol):
    """A source-owned plan yielding every response intended for replay.

    Fetch persists a response before returning it; yielding adds it to the
    manifest that a decoder sees. Fetched-but-unyielded successes remain cached
    for resume, not replay. Failed acquisitions fail the run even if unyielded.
    """

    source: snapshot.Source
    configuration: dict[str, pydantic.JsonValue]

    def run(self, context: Context) -> Iterator[snapshot.CaptureResult]: ...


def run_capture(
    adapter: Adapter,
    semester: snapshot.Semester,
    directory,
    *,
    resume=False,
    max_resume_age=datetime.timedelta(hours=24),
) -> snapshot.Manifest:
    with _archive.open_run(
        adapter.source,
        semester,
        adapter.configuration,
        directory,
        resume=resume,
        max_resume_age=max_resume_age,
        clock=_utc_now,
    ) as run:
        if run.manifest.status != snapshot.RunStatus.COMPLETE:
            for result in adapter.run(run):
                run._record(result)

    return run.manifest


def _utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)
