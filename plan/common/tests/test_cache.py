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
