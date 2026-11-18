"""Own archive lifetimes, verified reads, and immutable response publication.

Capture orchestration crosses this internal seam once per run. Source adapters
receive only the fetch/failure interface; they do not know paths, checksums,
progress publication, locks, or temporary-file lifetimes.
"""

import datetime
import fcntl
import gzip
import hashlib
import json
import os
import tempfile
import uuid
import zlib
from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import BinaryIO

import pydantic

from plan.scrape import snapshot
from plan.scrape.snapshot import _json_bytes, _request_id

MANIFEST_NAME = "snapshot.json"


class ArchiveError(ValueError):
    pass


def load_snapshot(path, *, require_complete=True) -> snapshot.Snapshot:
    path = Path(path)
    if path.is_dir():
        path /= MANIFEST_NAME

    manifest = _read_model(snapshot.Manifest, path)
    if require_complete and manifest.status != snapshot.RunStatus.COMPLETE:
        raise snapshot.SnapshotValidationError("snapshot acquisition is not complete")

    results = tuple(
        _load_result(path.parent, manifest.snapshot_id, stored)
        for stored in manifest.results
    )
    return snapshot.Snapshot(manifest, results)


@contextmanager
def locked_directory(directory, *, lock_name=".lock") -> Iterator[Path]:
    directory = Path(directory)
    _ensure_directory(directory)

    with (directory / lock_name).open("a", encoding="utf-8") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ArchiveError("another capture is using this directory") from error

        try:
            yield directory
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


@contextmanager
def open_run(
    source, semester, configuration, directory, *, resume, max_resume_age, clock
) -> Iterator["_CaptureRun"]:
    if max_resume_age <= datetime.timedelta():
        raise ArchiveError("max resume age must be positive")

    with locked_directory(directory) as root:
        run = _CaptureRun(
            source,
            semester,
            configuration,
            root,
            resume=resume,
            max_resume_age=max_resume_age,
            clock=clock,
        )
        try:
            if run.manifest.status == snapshot.RunStatus.COMPLETE:
                yield run
                return

            finished = False
            try:
                yield run
                finished = True
            except Exception as error:  # noqa: BLE001 - Preserve evidence when source discovery fails.
                run.manifest.errors.append(f"{type(error).__name__}: {error}")
            finally:
                if not finished and not run.manifest.errors:
                    run.manifest.errors.append("capture execution was interrupted")

                run._finish()
        finally:
            run._closed = True


class _CaptureRun:
    def __init__(
        self,
        source,
        semester,
        configuration,
        directory: Path,
        *,
        resume,
        max_resume_age,
        clock,
    ):
        self._directory = directory
        self._path = directory / MANIFEST_NAME
        self._clock = clock
        self._seen = set()
        self._unreported_failures: dict[str, str] = {}
        self._closed = False

        if resume:
            previous = load_snapshot(self._path, require_complete=False).manifest
            if (
                previous.source != source
                or previous.semester != semester
                or _json_bytes(previous.configuration) != _json_bytes(configuration)
            ):
                raise ArchiveError(
                    "resume source, semester, and configuration must match the existing run"
                )

            if (
                not datetime.timedelta()
                <= clock() - previous.started_at
                <= max_resume_age
            ):
                raise ArchiveError("run is too old to resume; start a new capture run")

            if previous.status == snapshot.RunStatus.COMPLETE:
                self.manifest = previous
                return

            attempts = directory / "attempts"
            _ensure_directory(attempts)
            _write_json(attempts / f"{uuid.uuid4().hex}.json", previous)
            self.manifest = previous.model_copy(
                update={
                    "status": snapshot.RunStatus.RUNNING,
                    "finished_at": None,
                    "results": [],
                    "errors": [],
                }
            )
        else:
            if any(entry.name != ".lock" for entry in directory.iterdir()):
                raise ArchiveError(
                    "run directory is not empty; use --resume or a new directory"
                )

            self.manifest = snapshot.Manifest(
                snapshot_id=uuid.uuid4(),
                source=source,
                semester=semester,
                configuration=configuration,
                started_at=clock(),
            )

        _write_json(self._path, self.manifest)

    def fetch(
        self,
        request: dict[str, pydantic.JsonValue],
        loader: Callable[[], snapshot.Payload],
    ) -> snapshot.CaptureResult:
        self._ensure_active()

        cached = _response_path(self._directory / "responses", _request_id(request))
        if cached.exists():
            result = _read_model(snapshot.CaptureResult, cached)
            if (
                result.run_id != self.manifest.snapshot_id
                or result.request != request
                or result.status != snapshot.ResultStatus.SUCCESS
            ):
                raise ArchiveError("cached result does not match this request and run")

            return result

        try:
            payload = loader()
            if not isinstance(payload, snapshot.Payload):
                raise TypeError("capture loaders must return Payload")
        except Exception as error:  # noqa: BLE001 - A source failure is acquisition evidence.
            payload = snapshot.Payload(
                data=None, error=f"{type(error).__name__}: {error}"
            )

        result = snapshot.CaptureResult(
            run_id=self.manifest.snapshot_id,
            request=request,
            fetched_at=self._clock(),
            status=snapshot.ResultStatus.SUCCESS
            if payload.error is None
            else snapshot.ResultStatus.FAILED,
            payload=payload,
        )
        self._store(result)
        if result.payload.error is not None:
            self._unreported_failures[_request_id(request)] = result.payload.error

        return result

    def failure(
        self, request: dict[str, pydantic.JsonValue], error: str
    ) -> snapshot.CaptureResult:
        return self.fetch(request, lambda: snapshot.Payload(data=None, error=error))

    def _record(self, result: snapshot.CaptureResult) -> None:
        self._ensure_active()

        stored = self._store(result)
        if stored.request_id in self._seen:
            raise ArchiveError("capture yielded the same request more than once")

        self._seen.add(stored.request_id)
        self.manifest.results.append(stored)
        if stored.status == snapshot.ResultStatus.FAILED:
            self._unreported_failures.pop(stored.request_id, None)

        _write_json(self._path, self.manifest)

    def _finish(self) -> None:
        self.manifest.errors.extend(
            f"unyielded failed acquisition {key}: {error}"
            for key, error in self._unreported_failures.items()
        )
        failed = self.manifest.errors or any(
            result.status == snapshot.ResultStatus.FAILED
            for result in self.manifest.results
        )
        self.manifest.status = (
            snapshot.RunStatus.FAILED if failed else snapshot.RunStatus.COMPLETE
        )
        self.manifest.finished_at = self._clock()

        # Progress is mutable, but publication must satisfy the envelope contract.
        self.manifest = snapshot.Manifest.model_validate_json(
            _json_bytes(self.manifest)
        )
        _write_json(self._path, self.manifest)

    def _store(self, result: snapshot.CaptureResult) -> snapshot._StoredResult:
        if result.run_id != self.manifest.snapshot_id:
            raise ArchiveError("capture yielded a result from another run")

        encoded = _json_bytes(result)
        digest = hashlib.sha256(encoded).hexdigest()
        key = _request_id(result.request)
        directory = self._directory / (
            "responses"
            if result.status == snapshot.ResultStatus.SUCCESS
            else "failures"
        )
        path = _response_path(
            directory, key if result.status == snapshot.ResultStatus.SUCCESS else digest
        )
        file = path.relative_to(self._directory).as_posix()
        _ensure_directory(path.parent)

        if path.exists():
            if _read_bytes(path) != encoded:
                raise ArchiveError("an archived response cannot be overwritten")
        else:
            _write_json(path, result)

        return snapshot._StoredResult(
            request_id=key, file=file, sha256=digest, status=result.status
        )

    def _ensure_active(self) -> None:
        if self._closed:
            raise ArchiveError("capture context is closed")


def _load_result(
    directory: Path, run_id: uuid.UUID, stored: snapshot._StoredResult
) -> snapshot.CaptureResult:
    path = directory / stored.file
    try:
        digest = hashlib.sha256(_read_bytes(path)).hexdigest()
    except (OSError, EOFError, zlib.error) as error:
        raise snapshot.SnapshotValidationError(
            f"cannot read archived result: {stored.file}"
        ) from error

    if digest != stored.sha256:
        raise snapshot.SnapshotValidationError(
            f"archived result checksum mismatch: {stored.file}"
        )

    result = _read_model(snapshot.CaptureResult, path)
    if (
        result.run_id != run_id
        or _request_id(result.request) != stored.request_id
        or result.status != stored.status
    ):
        raise snapshot.SnapshotValidationError(
            "archived result does not belong to this manifest"
        )

    return result


def _read_model[Model: pydantic.BaseModel](model: type[Model], path: Path) -> Model:
    try:
        # JSON mode admits timestamp/UUID strings without enabling lax coercions.
        data = json.loads(_read_bytes(path).decode("utf-8"))
        return model.model_validate_json(_json_bytes(data))
    except (
        OSError,
        EOFError,
        zlib.error,
        UnicodeError,
        ValueError,
        TypeError,
    ) as error:
        raise snapshot.SnapshotValidationError(
            f"cannot read {path}: {error}"
        ) from error


def _write_json(path: Path, data) -> None:
    encoded = _json_bytes(data)
    if path.suffix == ".gz":
        encoded = gzip.compress(encoded, compresslevel=6, mtime=0)

    with _atomic_writer(path) as stream:
        stream.write(encoded)


def _response_path(directory: Path, key: str) -> Path:
    # Retain existing plain files and references when resuming older runs.
    plain = directory / f"{key}.json"
    return plain if plain.exists() else directory / f"{key}.json.gz"


def _read_bytes(path: Path) -> bytes:
    encoded = path.read_bytes()
    return gzip.decompress(encoded) if path.suffix == ".gz" else encoded


def _ensure_directory(path: Path) -> None:
    if path.is_dir():
        return

    _ensure_directory(path.parent)
    try:
        path.mkdir(mode=0o750)
    except FileExistsError:
        if not path.is_dir():
            raise

    # Persist both the directory itself and the parent's new name entry.
    _sync_directory(path)
    _sync_directory(path.parent)


def _sync_directory(path: Path) -> None:
    with ExitStack() as cleanup:
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        cleanup.callback(os.close, fd)
        os.fsync(fd)


@contextmanager
def _atomic_writer(path: Path) -> Iterator[BinaryIO]:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
        ) as stream:
            temporary = Path(stream.name)
            yield stream
            stream.flush()
            os.fsync(stream.fileno())

        os.replace(temporary, path)
        _sync_directory(path.parent)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
