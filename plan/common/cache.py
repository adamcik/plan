import logging
from dataclasses import dataclass
from typing import Generic, TypeVar

from django.core.cache import caches
from opentelemetry import trace
from opentelemetry.trace import SpanKind

T = TypeVar("T")
_MISSING = object()
logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


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
        attributes = {
            "cache.layers": [name for name, _ttl in self.layers],
            "cache.key": key,
        }
        with tracer.start_as_current_span(
            "MULTI CACHE GET", kind=SpanKind.CLIENT, attributes=attributes
        ) as span:
            for name, ttl in self.layers:
                try:
                    value = self.backends[name].get(key, _MISSING)
                except Exception:
                    logger.exception(
                        "MultiCache backend get failed",
                        extra={"cache_layer": name},
                    )
                    continue

                if value is not _MISSING:
                    promoted = False
                    for missed_name, missed_ttl in missed:
                        try:
                            self.backends[missed_name].set(key, value, missed_ttl)
                            promoted = True
                        except Exception:
                            logger.exception(
                                "MultiCache backend promotion set failed",
                                extra={"cache_layer": missed_name},
                            )

                    span.set_attribute("cache.hit", True)
                    span.set_attribute("cache.hit.layer", name)
                    span.set_attribute("cache.miss.count", len(missed))
                    span.set_attribute("cache.promoted", promoted)
                    return CacheResult(hit=True, value=value)

                missed.append((name, ttl))

            span.set_attribute("cache.hit", False)
            span.set_attribute("cache.miss.count", len(missed))
            span.set_attribute("cache.promoted", False)
            return CacheResult(hit=False)

    def set(self, key: str, value: T) -> None:
        for name, ttl in self.layers:
            self.backends[name].set(key, value, ttl)

    def delete(self, key: str) -> None:
        for name, _ttl in self.layers:
            self.backends[name].delete(key)
