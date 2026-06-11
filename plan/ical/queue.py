import logging
import queue
import threading
from dataclasses import dataclass

from django.core.cache import caches
from django.http.response import HttpResponseBase

logger = logging.getLogger(__name__)

_MAX_QUEUE_SIZE = 32
_WORKER_GET_TIMEOUT_SECONDS = 0.5


@dataclass(frozen=True)
class QueuedCacheSet:
    cache_alias: str
    key: str
    value: object
    timeout: float | None


_lock = threading.Lock()
_tasks: queue.Queue[QueuedCacheSet] = queue.Queue(maxsize=_MAX_QUEUE_SIZE)
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
            task = _tasks.get(timeout=_WORKER_GET_TIMEOUT_SECONDS)
        except queue.Empty:
            continue

        try:
            caches[task.cache_alias].set(task.key, task.value, timeout=task.timeout)
        except Exception:
            logger.exception(
                "failed to persist queued cache entry",
                extra={"cache_alias": task.cache_alias, "key": task.key},
            )
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


def enqueue_cache_set(
    cache_alias: str,
    key: str,
    value,
    timeout: float | None,
) -> bool:
    _ensure_worker_started()
    task = QueuedCacheSet(
        cache_alias=cache_alias,
        key=key,
        value=_cacheable_value(value),
        timeout=timeout,
    )
    try:
        _tasks.put_nowait(task)
    except queue.Full:
        logger.warning(
            "dropping queued cache entry due to full queue",
            extra={"cache_alias": cache_alias, "key": key},
        )
        return False
    return True


def flush_for_tests() -> None:
    _tasks.join()
