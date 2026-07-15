"""Stable resource and log attributes shared by telemetry signals."""

import os
from threading import current_thread, get_ident
from typing import TYPE_CHECKING

from opentelemetry import trace

if TYPE_CHECKING:
    from plan.telemetry import TelemetrySettings


def resource_attributes(settings: "TelemetrySettings") -> dict[str, str | int]:
    attributes: dict[str, str | int] = {
        "service.name": settings.service_name,
        "service.version": settings.service_version,
        "deployment.environment.name": settings.deployment_environment,
        "process.pid": os.getpid(),
    }
    if settings.service_instance_id:
        attributes["service.instance.id"] = settings.service_instance_id
    if settings.vcs_revision:
        attributes["vcs.revision"] = settings.vcs_revision
    return attributes


def log_attributes() -> dict[str, str | int | bool]:
    thread = current_thread()
    attributes: dict[str, str | int | bool] = {
        "process.pid": os.getpid(),
        "process.thread.id": get_ident(),
        "process.thread.name": thread.name,
    }
    context = trace.get_current_span().get_span_context()
    if context.is_valid:
        attributes.update(
            trace_id=f"{context.trace_id:032x}",
            span_id=f"{context.span_id:016x}",
            trace_sampled=context.trace_flags.sampled,
        )
    return attributes
