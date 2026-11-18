"""The acquisition model, independent of storage and domain normalization.

Manifest identifies one run and records its Source, Semester, and configuration.
Payload belongs to a CaptureResult (one acquisition); the manifest references
its stored representation. Snapshot is the verified manifest and its results,
ready for an offline decoder. Acquisition success does not imply valid domain
data: courses and lectures are not part of this model.
"""

import hashlib
import json
import uuid
from dataclasses import dataclass
from enum import StrEnum
from functools import cached_property
from typing import Annotated, Literal, Self

import pydantic

_NonBlank = Annotated[str, pydantic.StringConstraints(pattern=r"\S")]
_Digest = Annotated[str, pydantic.StringConstraints(pattern=r"^[a-f0-9]{64}$")]


class SnapshotValidationError(ValueError):
    pass


class _Model(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(strict=True, extra="forbid", allow_inf_nan=False)


class RunStatus(StrEnum):
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


class ResultStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"


class Source(_Model):
    """Selects interpretation of source-owned requests and payloads.

    Its format version is independent of the generic envelope schema version.
    """

    name: _NonBlank
    format_version: Annotated[int, pydantic.Field(ge=1)]


class Semester(_Model):
    """An acquisition selection, not an existing row in Plan's database."""

    year: Annotated[int, pydantic.Field(ge=1900, le=9999)]
    type: Literal["spring", "fall"]


class Payload(_Model):
    """Opaque source data, including bodies from failed acquisitions.

    JSON null is valid data; error evidence, not a missing body, marks failure.
    """

    data: pydantic.JsonValue
    metadata: dict[str, pydantic.JsonValue] = pydantic.Field(default_factory=dict)
    error: _NonBlank | None = None


class CaptureResult(_Model):
    """One acquisition outcome; its payload need not be interpretable by Plan."""

    run_id: uuid.UUID
    request: dict[str, pydantic.JsonValue]
    fetched_at: pydantic.AwareDatetime
    status: ResultStatus
    payload: Payload

    @pydantic.model_validator(mode="after")
    def _validate_outcome(self) -> Self:
        if (self.status == ResultStatus.FAILED) != (self.payload.error is not None):
            raise ValueError("result status must agree with its error evidence")

        return self


class _StoredResult(_Model):
    """Internal file reference whose checksum identifies uncompressed JSON."""

    request_id: _Digest
    file: Annotated[
        str,
        pydantic.StringConstraints(
            pattern=r"^(responses|failures)/[a-f0-9]{64}\.json(?:\.gz)?$"
        ),
    ]
    sha256: _Digest
    status: ResultStatus


class Manifest(_Model):
    """Run selection, progress, and references to independently durable results.

    Complete means the acquisition plan finished without failures. An offline
    decoder still has to establish source completeness and validate domain data.
    """

    schema_version: Annotated[int, pydantic.Field(ge=1, le=1)] = 1
    snapshot_id: uuid.UUID
    source: Source
    semester: Semester
    configuration: dict[str, pydantic.JsonValue]
    started_at: pydantic.AwareDatetime
    finished_at: pydantic.AwareDatetime | None = None
    status: RunStatus = RunStatus.RUNNING
    results: list[_StoredResult] = pydantic.Field(default_factory=list)
    errors: list[_NonBlank] = pydantic.Field(default_factory=list)

    @pydantic.model_validator(mode="after")
    def _validate_run(self) -> Self:
        if (self.status == RunStatus.RUNNING) != (self.finished_at is None):
            raise ValueError("only unfinished runs may have no finished_at")

        if self.finished_at is not None and self.finished_at < self.started_at:
            raise ValueError("finished_at precedes started_at")

        keys = [result.request_id for result in self.results]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate request in manifest")

        failures = any(result.status == ResultStatus.FAILED for result in self.results)
        if self.status == RunStatus.COMPLETE and (self.errors or failures):
            raise ValueError("complete runs must contain no failures")

        if self.status == RunStatus.FAILED and not (self.errors or failures):
            raise ValueError("failed runs must describe a failure")

        return self


@dataclass(frozen=True)
class Snapshot:
    """Verified replay input, queried by opaque request rather than file layout."""

    manifest: Manifest
    results: tuple[CaptureResult, ...]

    def result_for(
        self, request: dict[str, pydantic.JsonValue]
    ) -> CaptureResult | None:
        return self._by_request.get(_request_id(request))

    @property
    def content_digest(self) -> str:
        data = {
            "manifest": self.manifest.model_dump(mode="json"),
            "results": [result.model_dump(mode="json") for result in self.results],
        }
        return hashlib.sha256(_json_bytes(data)).hexdigest()

    @cached_property
    def _by_request(self) -> dict[str, CaptureResult]:
        return {_request_id(result.request): result for result in self.results}


def _request_id(request: dict[str, pydantic.JsonValue]) -> str:
    return hashlib.sha256(_json_bytes(request)).hexdigest()


def _json_bytes(data) -> bytes:
    if isinstance(data, pydantic.BaseModel):
        data = data.model_dump(mode="json")

    return (
        json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        + "\n"
    ).encode()
