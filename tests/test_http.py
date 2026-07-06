"""Tests for HTTP retry/backoff utilities."""

import io
import sys
import unittest
import urllib.error
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib import http


class FakeResponse:
    def __init__(self, body: bytes = b"{}", status: int = 200):
        self._body = body
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self._body


def make_http_error(status: int, headers=None, body: bytes = b"error"):
    return urllib.error.HTTPError(
        url="https://example.test/search?access_token=secret",
        code=status,
        msg="error",
        hdrs=headers or {},
        fp=io.BytesIO(body),
    )


class TestBackoffHelpers(unittest.TestCase):
    def test_compute_delay_uses_exponential_backoff_with_jitter_and_cap(self):
        with patch("lib.http.random.uniform", return_value=0.5):
            self.assertEqual(http._compute_delay(0, base=2.0, cap=30.0), 2.5)
            self.assertEqual(http._compute_delay(4, base=2.0, cap=10.0), 10.0)

    def test_parse_retry_after_seconds(self):
        self.assertEqual(http._parse_retry_after("2.5"), 2.5)

    def test_parse_retry_after_http_date_caps_to_60_seconds(self):
        future = datetime.now(timezone.utc) + timedelta(seconds=120)
        parsed = http._parse_retry_after(format_datetime(future))
        self.assertIsNotNone(parsed)
        self.assertGreater(parsed, 0)
        self.assertLessEqual(parsed, 60.0)

    def test_parse_retry_after_invalid(self):
        self.assertIsNone(http._parse_retry_after("not a retry date"))


class TestRequestRetries(unittest.TestCase):
    def test_404_does_not_retry(self):
        opener = Mock(side_effect=make_http_error(404))
        with patch("lib.http.urllib.request.urlopen", opener), patch("lib.http.time.sleep") as sleep:
            with self.assertRaises(http.HTTPError):
                http.get("https://example.test/missing", retries=3)
        self.assertEqual(opener.call_count, 1)
        sleep.assert_not_called()

    def test_429_respects_retry_after_seconds(self):
        opener = Mock(side_effect=[
            make_http_error(429, headers={"Retry-After": "3"}),
            FakeResponse(b'{"ok": true}'),
        ])
        with patch("lib.http.urllib.request.urlopen", opener), patch("lib.http.time.sleep") as sleep:
            result = http.get("https://example.test/rate-limited", retries=2)
        self.assertEqual(result, {"ok": True})
        sleep.assert_called_once_with(3.0)

    def test_urlerror_uses_shared_backoff(self):
        opener = Mock(side_effect=[
            urllib.error.URLError("temporary dns failure"),
            FakeResponse(b'{"ok": true}'),
        ])
        with (
            patch("lib.http.urllib.request.urlopen", opener),
            patch("lib.http._compute_delay", return_value=4.0) as compute_delay,
            patch("lib.http.time.sleep") as sleep,
        ):
            result = http.get("https://example.test/transient", retries=2, backoff=3.0)
        self.assertEqual(result, {"ok": True})
        compute_delay.assert_called_once_with(0, base=3.0)
        sleep.assert_called_once_with(4.0)


if __name__ == "__main__":
    unittest.main()
