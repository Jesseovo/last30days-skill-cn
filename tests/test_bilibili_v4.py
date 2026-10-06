"""Bilibili v4: WBI signing, date window, risk-control fallback (#17)."""

import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from lib import bilibili, http  # noqa: E402

IMG_KEY = "7cd084941338484aae1ad9425b84077c"
SUB_KEY = "4932caff0ff746eab6f01bf08b70ac45"


def test_mixin_key_matches_documented_vector():
    assert bilibili.get_mixin_key(IMG_KEY + SUB_KEY) == "ea1db124af3c7062474693fa704f4ff8"


def test_sign_wbi_matches_documented_vector():
    signed = bilibili.sign_wbi({"foo": "114", "bar": "514", "zab": 1919810}, IMG_KEY, SUB_KEY, wts=1702204169)
    assert signed["w_rid"] == "8f6f2b5b3d485fe1886cec6a0be8c5d4"
    assert signed["wts"] == "1702204169"


def test_sign_wbi_strips_forbidden_characters():
    signed = bilibili.sign_wbi({"keyword": "AI(编程)!*'"}, IMG_KEY, SUB_KEY, wts=1)
    assert signed["keyword"] == "AI编程"


def test_parse_video_converts_duration_tags_and_counts():
    video = {
        "bvid": "BV1xx411c7mD", "title": "<em class=\"keyword\">AI</em>编程", "author": "UP主", "mid": 42,
        "pubdate": 1790985600, "duration": "1:02:03", "tag": "AI,编程", "play": "1234",
        "video_review": 5, "review": 6, "favorites": 7, "like": 8, "description": "<b>简介</b>",
    }
    parsed = bilibili._parse_video(video)
    assert parsed["url"] == "https://www.bilibili.com/video/BV1xx411c7mD"
    assert parsed["duration"] == 3723
    assert parsed["tags"] == ["AI", "编程"]
    assert parsed["engagement"] == {"views": 1234, "danmaku": 5, "comments": 6, "favorites": 7, "likes": 8}
    assert parsed["description"] == "简介"
    assert parsed["author_mid"] == "42"


def test_date_window_covers_whole_days_in_beijing_time():
    start, end = bilibili._date_window("2026-09-03", "2026-10-03")
    assert end - start == 30 * 86400 + 86399


class _FakeSession:
    """Minimal stand-in for http.Session used by search_bilibili."""

    def __init__(self, responses):
        self.responses = responses
        self.urls = []
        self.headers = {}

    def get_json(self, url, **kwargs):
        self.urls.append(url)
        for marker, response in self.responses:
            if marker in url:
                if isinstance(response, Exception):
                    raise response
                return response
        raise AssertionError(f"unexpected url {url}")

    def get_cookie(self, name):
        return "buvid"

    def set_cookie(self, *args, **kwargs):
        pass


NAV = {"data": {"wbi_img": {"img_url": f"https://i0.hdslb.com/bfs/wbi/{IMG_KEY}.png",
                             "sub_url": f"https://i0.hdslb.com/bfs/wbi/{SUB_KEY}.png"}}}
RESULT = {"code": 0, "data": {"result": [{"bvid": "BV1", "title": "AI编程助手", "pubdate": 1790985600}]}}


@pytest.fixture(autouse=True)
def _clear_wbi_cache():
    bilibili._wbi_cache.update({"keys": None, "at": 0.0})
    yield


def test_search_uses_wbi_and_date_window():
    session = _FakeSession([("/nav", NAV), ("/wbi/search/type", RESULT)])
    with patch.object(bilibili, "_new_session", return_value=session):
        items = bilibili.search_bilibili("AI编程助手", "2026-09-03", "2026-10-03", depth="quick")
    assert [i["bvid"] for i in items] == ["BV1"]
    assert items[0]["source"] == "wbi-search"
    search_url = [u for u in session.urls if "search/type" in u][0]
    assert "w_rid=" in search_url and "pubtime_begin_s=" in search_url and "pubtime_end_s=" in search_url


def test_risk_control_falls_back_to_legacy_endpoint():
    wbi_blocked = {"code": -412, "message": "request was banned"}
    first = _FakeSession([("/nav", NAV), ("/wbi/search/type", wbi_blocked)])
    second = _FakeSession([("/x/web-interface/search/type", RESULT)])
    with patch.object(bilibili, "_new_session", side_effect=[first, second]):
        items = bilibili.search_bilibili("AI编程助手", "2026-09-03", "2026-10-03", depth="quick")
    assert items and items[0]["source"] == "legacy-search"


def test_http_412_is_reported_when_every_path_fails():
    blocked = http.HTTPError("HTTP 412", 412)
    sessions = [_FakeSession([("/nav", NAV), ("search/type", blocked)]) for _ in range(2)]
    with patch.object(bilibili, "_new_session", side_effect=sessions), \
            patch("lib.crawler_bridge.is_playwright_available", return_value=False):
        with pytest.raises(http.HTTPError) as exc:
            bilibili.search_bilibili("AI编程助手", "2026-09-03", "2026-10-03", depth="quick")
    assert "风控" in str(exc.value)


def test_fetch_hot_parses_hotword_list():
    payload = {"list": [{"keyword": "G2 TL", "show_name": "G2战胜TL", "pos": 1, "heat_score": 99}]}
    session = _FakeSession([("hotword", payload)])
    with patch.object(bilibili, "_new_session", return_value=session):
        hot = bilibili.fetch_hot(10)
    assert hot[0]["title"] == "G2战胜TL"
    assert hot[0]["rank"] == 1
    assert "search.bilibili.com" in hot[0]["url"]
