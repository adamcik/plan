import pytest

from django.core.cache import caches

from plan.common.cache import CacheResult, MultiCache


@pytest.fixture
def cache_settings(settings):
    settings.CACHES = {
        "l1": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "test-l1",
        },
        "l2": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "test-l2",
        },
    }
    caches["l1"].clear()
    caches["l2"].clear()
    yield
    caches["l1"].clear()
    caches["l2"].clear()


@pytest.fixture
def cache(cache_settings) -> MultiCache[str]:
    return MultiCache[str](l1=60, l2=300)


def test_requires_at_least_one_layer():
    with pytest.raises(ValueError, match="MultiCache needs at least one layer"):
        MultiCache()


def test_set_writes_to_all_layers(cache: MultiCache[str]):
    cache.set("key", "value")

    assert caches["l1"].get("key") == "value"
    assert caches["l2"].get("key") == "value"


def test_get_promotes_fallback_hit_to_missed_layers(cache: MultiCache[str]):
    caches["l2"].set("key", "value", timeout=300)

    assert cache.get("key") == CacheResult(hit=True, value="value")
    assert caches["l1"].get("key") == "value"


def test_get_returns_miss_result(cache: MultiCache[str]):
    assert cache.get("missing") == CacheResult[str](hit=False)


def test_delete_removes_all_layers(cache: MultiCache[str]):
    cache.set("key", "value")

    cache.delete("key")

    assert caches["l1"].get("key") is None
    assert caches["l2"].get("key") is None


def test_get_can_distinguish_cached_none_from_miss(cache_settings):
    cache = MultiCache[str | None](l1=60, l2=300)
    cache.set("key", None)

    assert cache.get("key") == CacheResult[str | None](hit=True, value=None)


def test_init_requires_configured_cache_names(cache_settings):
    with pytest.raises(ValueError, match="could not find cache layer 'missing'"):
        MultiCache(l1=60, missing=300)
