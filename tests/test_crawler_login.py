"""Browser layer v4: login persistence, cookie import, circuit breaker (#8 #11 #13)."""

import json
import os
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from lib import crawler_bridge  # noqa: E402


@pytest.fixture
def cookie_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(crawler_bridge, "COOKIE_DIR", tmp_path)
    return tmp_path


@pytest.fixture(autouse=True)
def _reset_breaker():
    crawler_bridge.reset_browser_failure()
    crawler_bridge._playwright_available = None
    yield
    crawler_bridge.reset_browser_failure()
    crawler_bridge._playwright_available = None


def test_import_cookie_header_requires_login_cookie(cookie_dir):
    with pytest.raises(ValueError) as exc:
        crawler_bridge.import_cookie_header("zhihu", "_xsrf=1; d_c0=2")
    assert "z_c0" in str(exc.value)

    count = crawler_bridge.import_cookie_header("zhihu", "_xsrf=1; z_c0=secret")
    assert count == 2
    saved = json.loads((cookie_dir / "zhihu_cookies.json").read_text(encoding="utf-8"))
    assert {c["name"] for c in saved} == {"_xsrf", "z_c0"}
    assert all(c["domain"] == ".zhihu.com" for c in saved)
    assert crawler_bridge.has_login("zhihu")


def test_weibo_cookie_import_covers_both_domains(cookie_dir):
    crawler_bridge.import_cookie_header("weibo", "SUB=abc; SUBP=def")
    domains = {c["domain"] for c in crawler_bridge.load_cookies("weibo")}
    assert domains == {".weibo.cn", ".weibo.com"}


def test_ambiguous_platforms_need_a_login_marker(cookie_dir):
    # Anonymous XHS visitors also get a web_session cookie.
    crawler_bridge.save_cookies("xiaohongshu", [{"name": "web_session", "value": "guest", "domain": ".xiaohongshu.com", "expires": -1}])
    assert not crawler_bridge.has_login("xiaohongshu")
    crawler_bridge._write_marker("xiaohongshu", "browser")
    assert crawler_bridge.has_login("xiaohongshu")
    crawler_bridge.mark_logged_out("xiaohongshu")
    assert not crawler_bridge.has_login("xiaohongshu")


def test_expired_login_cookie_is_not_a_login(cookie_dir):
    crawler_bridge.save_cookies("bilibili", [{"name": "SESSDATA", "value": "x", "domain": ".bilibili.com", "expires": time.time() - 10}])
    assert not crawler_bridge.has_login("bilibili")
    crawler_bridge.save_cookies("bilibili", [{"name": "SESSDATA", "value": "x", "domain": ".bilibili.com", "expires": time.time() + 86400 * 30}])
    status = crawler_bridge.login_status("bilibili")
    assert status["logged_in"] and status["expires"]


def test_has_login_does_not_create_directories(tmp_path, monkeypatch):
    missing = tmp_path / "nope"
    monkeypatch.setattr(crawler_bridge, "COOKIE_DIR", missing)
    assert not crawler_bridge.has_login("douyin")
    assert not missing.exists()


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits")
def test_cookie_files_are_private(cookie_dir):
    crawler_bridge.save_cookies("douyin", [{"name": "sessionid", "value": "x"}])
    mode = (cookie_dir / "douyin_cookies.json").stat().st_mode & 0o777
    assert mode == 0o600


def test_circuit_breaker_disables_browser_for_the_run(capsys):
    with patch.dict(os.environ, {"LAST30DAYS_DISABLE_BROWSER": ""}):
        crawler_bridge._playwright_available = True
        assert crawler_bridge.is_playwright_available()
        crawler_bridge._mark_browser_failure("Executable doesn't exist at /old/chromium")
        crawler_bridge._mark_browser_failure("second failure is not reported again")
        assert not crawler_bridge.is_playwright_available()
        assert crawler_bridge.browser_failure().startswith("Executable")
    err = capsys.readouterr().err
    assert err.count("无法启动") == 1
    assert "LAST30DAYS_BROWSER_PATH" in err and "LAST30DAYS_DISABLE_BROWSER" in err


def test_disable_env_turns_browser_off(monkeypatch):
    monkeypatch.setenv("LAST30DAYS_DISABLE_BROWSER", "1")
    assert not crawler_bridge.is_playwright_available()
    assert crawler_bridge._browser_status()["mode"] == "disabled"
    ok, message = crawler_bridge.interactive_login("xiaohongshu")
    assert not ok and "--cookie" in message


def test_interactive_login_rejects_unknown_platform():
    ok, message = crawler_bridge.interactive_login("myspace")
    assert not ok and "xiaohongshu" in message


@pytest.mark.parametrize("system,expected", [
    ("Darwin", "Macintosh"), ("Linux", "X11; Linux"), ("Windows", "Windows NT 10.0"),
])
def test_ua_follows_real_browser_version_and_os(system, expected):
    with patch.object(crawler_bridge.platform_mod, "system", return_value=system):
        ua = crawler_bridge._ua_for_browser("141.0.7390.54", mobile=False)
    assert expected in ua and "Chrome/141.0.0.0" in ua and "(KHTML, like Gecko)" in ua
    assert crawler_bridge._ua_for_browser("", mobile=False) == crawler_bridge._DESKTOP_UA
    assert "iPhone" in crawler_bridge._ua_for_browser("141.0", mobile=True)


def test_xhs_note_card_parser_keeps_xsec_token_and_camel_case():
    raw = {"id": "65a1b2c3d4e5f60718293a4b", "xsec_token": "tok",
           "note_card": {"display_title": "标题", "user": {"nickname": "n"},
                         "interact_info": {"liked_count": "1.2万", "comment_count": "3"}}}
    parsed = crawler_bridge._parse_crawler_xhs_note(raw)
    assert parsed["url"].endswith("?xsec_token=tok&xsec_source=pc_search")
    assert parsed["engagement"]["likes"] == 12000 and parsed["engagement"]["comments"] == 3
    camel = {"id": "65a1b2c3d4e5f60718293a4c", "noteCard": {"displayTitle": "驼峰", "interactInfo": {"likedCount": 7}}}
    assert crawler_bridge._extract_xhs_note_items({"data": {"items": [camel]}}) == [camel]
    assert crawler_bridge._parse_crawler_xhs_note(camel)["title"] == "驼峰"


def test_crawler_status_lists_login_state(cookie_dir):
    crawler_bridge.import_cookie_header("douyin", "sessionid=1")
    status = crawler_bridge.get_crawler_status()
    assert "douyin" in status["cached_logins"]
    assert status["logins"]["douyin"]["logged_in"] is True
    assert status["logins"]["douyin"]["login_method"] == "cookie-import"
