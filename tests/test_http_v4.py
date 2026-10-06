"""v4 HTTP layer: complete UAs (#17), 412 handling, decoding, cookie sessions."""

import gzip
import io
import os
import sys
import urllib.error
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from lib import http  # noqa: E402


class FakeResponse:
    def __init__(self, body=b"{}", status=200, headers=None, url="https://example.test/"):
        self._body = body
        self.status = status
        self.headers = headers or {}
        self._url = url

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._body

    def geturl(self):
        return self._url


def test_browser_uas_are_complete_issue_17():
    # The WAF answer to "Mozilla/5.0 (...) AppleWebKit/537.36" was HTTP 412.
    for ua in (http.DESKTOP_UA, http.MAC_UA):
        assert "(KHTML, like Gecko)" in ua and "Chrome/" in ua and ua.endswith("Safari/537.36")
    assert "Mobile/" in http.MOBILE_UA and "Safari/" in http.MOBILE_UA


def test_browser_headers_are_consistent_with_ua(monkeypatch):
    monkeypatch.delenv("LAST30DAYS_USER_AGENT", raising=False)
    headers = http.browser_headers(referer="https://search.bilibili.com/", accept="json")
    assert headers["User-Agent"] == http.DESKTOP_UA
    assert f'v="{http.CHROME_MAJOR}"' in headers["Sec-Ch-Ua"]
    assert headers["Origin"] == "https://search.bilibili.com"
    assert headers["Accept"].startswith("application/json")
    assert "br" not in headers["Accept-Encoding"]  # stdlib cannot decode brotli


def test_user_agent_override(monkeypatch):
    monkeypatch.setenv("LAST30DAYS_USER_AGENT", "Mozilla/5.0 custom Chrome/150.0.0.0 Safari/537.36")
    headers = http.browser_headers()
    assert headers["User-Agent"].startswith("Mozilla/5.0 custom")
    assert 'v="150"' in headers["Sec-Ch-Ua"]


def test_412_fails_fast_with_clear_message():
    error = urllib.error.HTTPError("https://api.bilibili.com/x", 412, "Precondition Failed", {}, io.BytesIO(b""))
    opener = Mock(side_effect=error)
    with patch("lib.http.urllib.request.urlopen", opener), patch("lib.http.time.sleep") as sleep:
        try:
            http.get("https://api.bilibili.com/x", retries=3)
        except http.HTTPError as exc:
            assert exc.status_code == 412
            assert exc.code == 412
            assert "WAF" in str(exc)
        else:
            raise AssertionError("expected HTTPError")
    assert opener.call_count == 1
    sleep.assert_not_called()


def test_gzip_and_gbk_bodies_are_decoded():
    text = "中文页面"
    raw = gzip.compress(text.encode("gbk"))
    response = FakeResponse(raw, headers={"Content-Encoding": "gzip", "Content-Type": "text/html; charset=GBK"})
    with patch("lib.http.urllib.request.urlopen", Mock(return_value=response)):
        assert http.get_text("https://example.test/") == text


def test_fetch_returns_final_url():
    response = FakeResponse(b"<html></html>", url="https://www.bing.com/?q=x")
    with patch("lib.http.urllib.request.urlopen", Mock(return_value=response)):
        status, final_url, body = http.fetch("https://cn.bing.com/search?q=x")
    assert status == 200
    assert final_url == "https://www.bing.com/?q=x"
    assert body == "<html></html>"


def test_session_cookie_helpers():
    session = http.Session()
    assert session.load_cookie_header("SESSDATA=abc; buvid3=xyz; broken", ".bilibili.com") == 2
    assert session.get_cookie("buvid3") == "xyz"
    assert {"SESSDATA", "buvid3"} <= session.cookie_names()


def test_debug_flag_is_read_dynamically(monkeypatch, capsys):
    monkeypatch.setenv("LAST30DAYS_DEBUG", "1")
    http.log("hello")
    assert "[DEBUG] hello" in capsys.readouterr().err
    monkeypatch.setenv("LAST30DAYS_DEBUG", "0")
    http.log("quiet")
    assert "quiet" not in capsys.readouterr().err


def test_redact_url_hides_cookie_and_tokens():
    redacted = http._redact_url("https://x.test/a?access_token=1&SESSDATA=2&q=ok")
    assert "access_token=%2A%2A%2A" in redacted and "SESSDATA=%2A%2A%2A" in redacted and "q=ok" in redacted
