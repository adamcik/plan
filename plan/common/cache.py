import logging
from dataclasses import dataclass
from typing import Generic, TypeVar

from django.core.cache import caches

T = TypeVar("T")
_MISSING = object()
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CacheResult(Generic[T]):
    hit: bool
    value: T | None = None


class MultiCache(Generic[T]):
    def __init__(self, **layers: int | None) -> None:
        if not layers:
            raise ValueError("MultiCache needs at least one layer")

        self.layers = tuple(layers.items())
        self.backends = {}
        for name, _ttl in self.layers:
            try:
                self.backends[name] = caches[name]
            except Exception as exc:
                raise ValueError(
                    "MultiCache.__init__ could not find cache layer "
                    f"{name!r}. Check Django CACHES configuration for that key."
                ) from exc

    def get(self, key: str) -> CacheResult[T]:
        missed: list[tuple[str, int | None]] = []

        for name, ttl in self.layers:
            try:
                value = self.backends[name].get(key, _MISSING)
            except Exception:
                logger.exception(
                    "MultiCache backend get failed",
                    extra={"cache_layer": name, "cache_key": key},
                )
                continue

            if value is not _MISSING:
                for missed_name, missed_ttl in missed:
                    try:
                        self.backends[missed_name].set(key, value, missed_ttl)
                    except Exception:
                        logger.exception(
                            "MultiCache backend promotion set failed",
                            extra={
                                "cache_layer": missed_name,
                                "cache_key": key,
                            },
                        )

                return CacheResult(hit=True, value=value)

            missed.append((name, ttl))

        return CacheResult(hit=False)

    def set(self, key: str, value: T) -> None:
        for name, ttl in self.layers:
            self.backends[name].set(key, value, ttl)

    def delete(self, key: str) -> None:
        for name, _ttl in self.layers:
            self.backends[name].delete(key)
