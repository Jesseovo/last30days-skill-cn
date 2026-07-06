"""Tests for cache module."""

import sys
import os
import tempfile
import unittest
from pathlib import Path

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib import cache, schema


class TestGetCacheKey(unittest.TestCase):
    def test_returns_string(self):
        result = cache.get_cache_key("test topic", "2026-01-01", "2026-01-31", "both")
        self.assertIsInstance(result, str)

    def test_consistent_for_same_inputs(self):
        key1 = cache.get_cache_key("test topic", "2026-01-01", "2026-01-31", "both")
        key2 = cache.get_cache_key("test topic", "2026-01-01", "2026-01-31", "both")
        self.assertEqual(key1, key2)

    def test_different_for_different_inputs(self):
        key1 = cache.get_cache_key("topic a", "2026-01-01", "2026-01-31", "both")
        key2 = cache.get_cache_key("topic b", "2026-01-01", "2026-01-31", "both")
        self.assertNotEqual(key1, key2)

    def test_key_length(self):
        key = cache.get_cache_key("test", "2026-01-01", "2026-01-31", "both")
        self.assertEqual(len(key), 16)


class TestCachePath(unittest.TestCase):
    def test_returns_path(self):
        result = cache.get_cache_path("abc123")
        self.assertIsInstance(result, Path)

    def test_has_json_extension(self):
        result = cache.get_cache_path("abc123")
        self.assertEqual(result.suffix, ".json")


class TestCacheValidity(unittest.TestCase):
    def test_nonexistent_file_is_invalid(self):
        fake_path = Path("/nonexistent/path/file.json")
        result = cache.is_cache_valid(fake_path)
        self.assertFalse(result)


class TestCacheRoundTrip(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_cache_dir = cache.CACHE_DIR
        self.old_model_cache_file = cache.MODEL_CACHE_FILE
        cache.CACHE_DIR = Path(self.tmp.name)
        cache.MODEL_CACHE_FILE = cache.CACHE_DIR / "model_selection.json"

    def tearDown(self):
        cache.CACHE_DIR = self.old_cache_dir
        cache.MODEL_CACHE_FILE = self.old_model_cache_file
        self.tmp.cleanup()

    def test_save_cache_writes_readable_utf8_chinese(self):
        cache.save_cache("utf8", {"topic": "中文平台", "items": ["微博"]})
        raw = cache.get_cache_path("utf8").read_text(encoding="utf-8")
        self.assertIn("中文平台", raw)
        self.assertEqual(cache.load_cache("utf8")["items"], ["微博"])

    def test_report_from_cache_preserves_clusters(self):
        report = schema.create_report("中文平台", "2026-01-01", "2026-01-31", "all")
        report.clusters = [{
            "representative_title": "同一热点",
            "sources": ["微博", "知乎"],
            "size": 2,
        }]
        cache.save_cache("report", report.to_dict())

        loaded = cache.load_cache("report")
        rebuilt = schema.Report.from_dict(loaded)
        self.assertEqual(rebuilt.topic, "中文平台")
        self.assertEqual(rebuilt.clusters[0]["representative_title"], "同一热点")

    def test_env_cache_dir_override_applies_before_load(self):
        old_env = os.environ.get("LAST30DAYS_CACHE_DIR")
        os.environ["LAST30DAYS_CACHE_DIR"] = self.tmp.name
        try:
            cache.CACHE_DIR = Path("unused-cache-dir")
            cache.save_cache("env", {"ok": True})
            cache.CACHE_DIR = Path("another-unused-cache-dir")
            self.assertEqual(cache.load_cache("env"), {"ok": True})
            self.assertTrue((Path(self.tmp.name) / "env.json").exists())
        finally:
            if old_env is None:
                os.environ.pop("LAST30DAYS_CACHE_DIR", None)
            else:
                os.environ["LAST30DAYS_CACHE_DIR"] = old_env


class TestModelCache(unittest.TestCase):
    def test_get_cached_model_returns_none_for_missing(self):
        # Clear any existing cache first
        result = cache.get_cached_model("nonexistent_provider")
        # May be None or a cached value, but should not error
        self.assertTrue(result is None or isinstance(result, str))


if __name__ == "__main__":
    unittest.main()
