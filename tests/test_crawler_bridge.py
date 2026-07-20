"""Tests for crawler_bridge module."""

import builtins
import importlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

# Add scripts to path (lib resolves under scripts/)
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import lib.crawler_bridge as crawler_bridge


def _reset_playwright_cache():
    crawler_bridge._playwright_available = None


class TestIsPlaywrightAvailable(unittest.TestCase):
    def tearDown(self):
        _reset_playwright_cache()

    def test_is_playwright_available(self):
        _reset_playwright_cache()
        real_import = builtins.__import__

        def import_playwright_fails(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "playwright.sync_api":
                raise ImportError("mock: playwright not installed")
            return real_import(name, globals, locals, fromlist, level)

        with patch.object(builtins, "__import__", side_effect=import_playwright_fails):
            importlib.reload(crawler_bridge)
            self.assertFalse(crawler_bridge.is_playwright_available())

        importlib.reload(crawler_bridge)


class TestParseCount(unittest.TestCase):
    def test_parse_count(self):
        p = crawler_bridge._parse_count
        self.assertEqual(p("1.2万"), 12000)
        self.assertEqual(p("1.2w"), 12000)
        self.assertEqual(p("1.2W"), 12000)
        self.assertEqual(p("12k"), 12000)
        self.assertEqual(p("12K"), 12000)
        self.assertEqual(p("1000"), 1000)
        self.assertEqual(p("1,234"), 1234)
        self.assertEqual(p("1亿"), 100000000)
        self.assertEqual(p("2.5亿"), 250000000)
        self.assertEqual(p(""), 0)
        self.assertEqual(p(None), 0)


class TestParseRelativeDate(unittest.TestCase):
    def test_parse_relative_date(self):
        fixed_now = datetime(2026, 4, 10, 15, 30, 0)
        prd = crawler_bridge._parse_relative_date

        with patch("lib.crawler_bridge.datetime") as mock_dt:
            mock_dt.now.return_value = fixed_now
            mock_dt.strptime = datetime.strptime

            self.assertEqual(
                prd("Thu Apr 10 10:00:00 +0800 2026"),
                "2026-04-10",
            )
            self.assertEqual(prd("10分钟前"), "2026-04-10")
            self.assertEqual(prd("3小时前"), "2026-04-10")
            self.assertEqual(prd("昨天"), "2026-04-09")
            self.assertEqual(prd("04-09"), "2026-04-09")
            self.assertIsNone(prd(""))
            self.assertIsNone(prd(None))


class TestGetCrawlerStatus(unittest.TestCase):
    def tearDown(self):
        _reset_playwright_cache()

    def test_get_crawler_status(self):
        cookie_dir = Path(tempfile.mkdtemp())
        try:
            (cookie_dir / "weibo_cookies.json").write_text("[]", encoding="utf-8")
            with patch.object(crawler_bridge, "COOKIE_DIR", cookie_dir):
                with patch.object(
                    crawler_bridge,
                    "is_playwright_available",
                    return_value=True,
                ):
                    status = crawler_bridge.get_crawler_status()

            self.assertIsInstance(status, dict)
            self.assertIn("playwright_available", status)
            self.assertIn("cached_logins", status)
            self.assertIn("cookie_dir", status)
            self.assertIn("browser", status)
            self.assertTrue(status["playwright_available"])
            self.assertEqual(status["cookie_dir"], str(cookie_dir))
            self.assertIn("weibo", status["cached_logins"])
        finally:
            shutil.rmtree(cookie_dir, ignore_errors=True)


class TestCleanHtml(unittest.TestCase):
    def test_clean_html(self):
        clean = crawler_bridge._clean_html
        self.assertEqual(clean(""), "")
        self.assertEqual(clean("a <b>b</b> c"), "a b c")
        self.assertEqual(clean("  foo   bar  "), "foo bar")


class TestXiaohongshuPayload(unittest.TestCase):
    def test_recommendation_payload_is_not_a_note_result(self):
        payload = {
            "code": 0,
            "success": True,
            "data": {"sug_items": [{"text": "咖啡店", "search_type": "notes"}]},
        }
        self.assertEqual(crawler_bridge._extract_xhs_note_items(payload), [])

    def test_note_card_payload_is_detected_and_normalized(self):
        payload = {
            "data": {
                "items": [{
                    "id": "abc123",
                    "note_card": {
                        "display_title": "咖啡店探店",
                        "desc": "周末去哪里喝咖啡",
                        "user": {"nickname": "小明", "user_id": "u1"},
                        "interact_info": {"liked_count": "1.2万"},
                    },
                }]
            }
        }
        records = crawler_bridge._extract_xhs_note_items(payload)
        parsed = crawler_bridge._parse_crawler_xhs_note(records[0])
        self.assertEqual(len(records), 1)
        self.assertEqual(parsed["title"], "咖啡店探店")
        self.assertEqual(parsed["engagement"]["likes"], 12000)
        self.assertTrue(parsed["url"].endswith("/abc123"))

    def test_external_browser_path_is_used(self):
        with patch.dict(
            "os.environ",
            {"LAST30DAYS_BROWSER_PATH": "~/Applications/Chromium", "LAST30DAYS_BROWSER_CHANNEL": ""},
            clear=False,
        ):
            kwargs = crawler_bridge._browser_launch_kwargs()
            status = crawler_bridge._browser_status()
        self.assertEqual(
            os.path.normpath(kwargs["executable_path"]),
            os.path.normpath(str(Path.home() / "Applications" / "Chromium")),
        )
        self.assertEqual(status["mode"], "external-path")


class TestLoadCookiesMissingFile(unittest.TestCase):
    def test_load_cookies_missing_file(self):
        d = Path(tempfile.mkdtemp())
        try:
            with patch.object(crawler_bridge, "COOKIE_DIR", d):
                self.assertIsNone(crawler_bridge.load_cookies("nonexistent_platform"))
        finally:
            shutil.rmtree(d, ignore_errors=True)


class TestSaveAndLoadCookies(unittest.TestCase):
    def test_save_and_load_cookies(self):
        cookies = [{"name": "session", "value": "abc", "domain": ".example.com"}]
        d = Path(tempfile.mkdtemp())
        try:
            with patch.object(crawler_bridge, "COOKIE_DIR", d):
                crawler_bridge.save_cookies("weibo", cookies)
                loaded = crawler_bridge.load_cookies("weibo")

            self.assertEqual(loaded, cookies)
            path = d / "weibo_cookies.json"
            self.assertTrue(path.exists())
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), cookies)
        finally:
            shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
