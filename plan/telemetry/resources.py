"""Stable resource and log attributes shared by telemetry signals."""

import importlib
import os
from threading import current_thread, get_ident

from opentelemetry import trace


def _uwsgi_worker_id() -> int | None:
    try:
        uwsgi = importlib.import_module("uwsgi")
    except ImportError:
        return None

    worker_id = getattr(uwsgi, "worker_id", None)
    if not callable(worker_id):
        return None

    value = worker_id()
    return value if isinstance(value, int) and not isinstance(value, bool) else None


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
