import logging
import queue
import threading

from django.core.cache import caches
from django.http.response import HttpResponseBase

logger = logging.getLogger(__name__)

_MAX_QUEUE_SIZE = 32
_WORKER_GET_TIMEOUT_SECONDS = 0.5

_lock = threading.Lock()
_tasks: queue.Queue[tuple[str, object, float | None]] = queue.Queue(
    maxsize=_MAX_QUEUE_SIZE
)
_worker_thread: threading.Thread | None = None


def _cacheable_value(value):
    if isinstance(value, HttpResponseBase):
        return value.__class__(
            value.content,
            status=value.status_code,
            headers=value.headers,
        )
    return value


def _worker() -> None:
    while True:
        try:
            key, value, timeout = _tasks.get(timeout=_WORKER_GET_TIMEOUT_SECONDS)
        except queue.Empty:
            continue

        try:
            caches["ical"].set(key, value, timeout=timeout)
        except Exception:
            logger.exception("failed to persist iCal cache entry", extra={"key": key})
        finally:
            _tasks.task_done()


def _ensure_worker_started() -> None:
    global _worker_thread
    if _worker_thread and _worker_thread.is_alive():
        return

    with _lock:
        if _worker_thread and _worker_thread.is_alive():
            return

        _worker_thread = threading.Thread(
            target=_worker,
            name="ical-cache-writer",
            daemon=True,
        )
        _worker_thread.start()


def enqueue_cache_set(key: str, value, timeout: float | None) -> bool:
    _ensure_worker_started()
    try:
        _tasks.put_nowait((key, _cacheable_value(value), timeout))
    except queue.Full:
        logger.warning(
            "dropping iCal cache entry due to full queue", extra={"key": key}
        )
        return False
    return True


def flush_for_tests() -> None:
    _tasks.join()
