from dataclasses import dataclass
from typing import Generic, TypeVar

from django.core.cache import caches

T = TypeVar("T")
_MISSING = object()


@dataclass(frozen=True)
class CacheResult(Generic[T]):
    hit: bool
    value: T | None = None


class MultiCache(Generic[T]):
    def __init__(self, **layers: int | None) -> None:
        if not layers:
            raise ValueError("MultiCache needs at least one layer")

        self.layers = tuple(layers.items())
        self.backends = {name: caches[name] for name in layers}

    def get(self, key: str) -> CacheResult[T]:
        missed: list[tuple[str, int | None]] = []

        for name, ttl in self.layers:
            value = self.backends[name].get(key, _MISSING)

            if value is not _MISSING:
                for missed_name, missed_ttl in missed:
                    self.backends[missed_name].set(key, value, missed_ttl)

                return CacheResult(hit=True, value=value)

            missed.append((name, ttl))

        return CacheResult(hit=False)

    def set(self, key: str, value: T) -> None:
        for name, ttl in self.layers:
            self.backends[name].set(key, value, ttl)

    def delete(self, key: str) -> None:
        for name, _ttl in self.layers:
            self.backends[name].delete(key)
