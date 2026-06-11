from unittest import mock

from django.core.cache import caches
from django.test import TestCase, override_settings

from plan.common.cache import CacheResult, MultiCache


@override_settings(
    CACHES={
        "l1": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "test-l1",
        },
        "l2": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "test-l2",
        },
    }
)
class MultiCacheTestCase(TestCase):
    def setUp(self):
        caches["l1"].clear()
        caches["l2"].clear()
        self.cache = MultiCache[str](l1=60, l2=300)

    def test_requires_at_least_one_layer(self):
        with self.assertRaises(ValueError):
            MultiCache()

    def test_set_writes_to_all_layers(self):
        self.cache.set("key", "value")

        self.assertEqual("value", caches["l1"].get("key"))
        self.assertEqual("value", caches["l2"].get("key"))

    def test_get_promotes_fallback_hit_to_missed_layers(self):
        caches["l2"].set("key", "value", timeout=300)

        self.assertEqual(CacheResult(hit=True, value="value"), self.cache.get("key"))
        self.assertEqual("value", caches["l1"].get("key"))

    def test_get_returns_miss_result(self):
        self.assertEqual(CacheResult[str](hit=False), self.cache.get("missing"))

    def test_delete_removes_all_layers(self):
        self.cache.set("key", "value")

        self.cache.delete("key")

        self.assertIsNone(caches["l1"].get("key"))
        self.assertIsNone(caches["l2"].get("key"))

    def test_get_can_distinguish_cached_none_from_miss(self):
        cache = MultiCache[str | None](l1=60, l2=300)
        cache.set("key", None)

        self.assertEqual(
            CacheResult[str | None](hit=True, value=None), cache.get("key")
        )

    def test_init_requires_configured_cache_names(self):
        with self.assertRaisesRegex(
            ValueError, "missing.*Check Django CACHES|could not find"
        ):
            MultiCache(l1=60, missing=300)

    def test_get_treats_backend_get_failure_as_miss(self):
        caches["l2"].set("key", "value", timeout=300)
        l1_backend = mock.Mock()
        l1_backend.get.side_effect = RuntimeError("boom")
        l1_backend.set = mock.Mock()

        self.cache.backends["l1"] = l1_backend

        self.assertEqual(CacheResult(hit=True, value="value"), self.cache.get("key"))
        self.assertIsNone(caches["l1"].get("key"))
        l1_backend.set.assert_not_called()

    def test_get_ignores_promotion_set_failure(self):
        caches["l2"].set("key", "value", timeout=300)
        l1_backend = mock.Mock()
        l1_backend.get.side_effect = lambda key, default=None: default
        l1_backend.set.side_effect = RuntimeError("boom")

        self.cache.backends["l1"] = l1_backend

        self.assertEqual(CacheResult(hit=True, value="value"), self.cache.get("key"))
