"""Site-search fallbacks now go through lib.websearch (multi-engine + validation)."""

import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from lib import douyin, env, normalize, toutiao, websearch, xiaohongshu, zhihu  # noqa: E402
from lib.websearch import SearchResult  # noqa: E402


@pytest.fixture(autouse=True)
def _fast_websearch(monkeypatch):
    websearch.reset_state()
    monkeypatch.setattr(websearch, "MIN_INTERVAL_SECONDS", 0)
    yield
    websearch.reset_state()


def _engines(results_by_engine):
    """Fake engine table: engine name -> list of SearchResult (or exception)."""
    def make(name):
        def run(query, timeout):
            value = results_by_engine.get(name, [])
            if isinstance(value, Exception):
                raise value
            return value
        return run
    return {name: make(name) for name in ("bing_cn", "ddg", "bing")}


def test_xiaohongshu_site_search_keeps_only_note_urls():
    fake = _engines({
        "bing_cn": [
            SearchResult("小红书 AI 工具测评", "https://www.xiaohongshu.com/explore/65a1b2c3d4e5f60718293a4b", "AI 工具测评摘要", "bing_cn"),
            SearchResult("AI 工具 招聘", "https://job.xiaohongshu.com/campus/position/1", "AI 工具 岗位", "bing_cn"),
        ],
    })
    with patch.dict(websearch._ENGINE_FUNCS, fake):
        items = xiaohongshu._search_via_site_search("AI 工具", 5)

    assert len(items) == 1
    assert items[0]["title"] == "小红书 AI 工具测评"
    assert items[0]["source"] == "site-search:bing_cn"
    assert items[0]["url"].endswith("/65a1b2c3d4e5f60718293a4b")


def test_zhihu_site_search_falls_through_blocked_engine():
    fake = _engines({
        "bing_cn": websearch.EngineBlocked("homepage"),
        "ddg": [SearchResult("知乎 AI 工具讨论 - 知乎", "https://www.zhihu.com/question/123456", "AI 工具 讨论", "ddg")],
    })
    with patch.dict(websearch._ENGINE_FUNCS, fake):
        items = zhihu._search_via_site_search("AI 工具", 5)

    assert len(items) == 1
    assert items[0]["title"] == "知乎 AI 工具讨论"
    assert items[0]["content_type"] == "question"
    assert "bing_cn" in websearch.blocked_engines()


def test_douyin_site_search_rejects_irrelevant_decoys():
    # Bing sometimes serves unrelated "decoy" results to automated clients.
    fake = _engines({
        "bing_cn": [SearchResult("体育赛事地图", "https://www.douyin.com/video/7234567890", "活动地图", "bing_cn")],
        "ddg": [SearchResult("抖音 AI 编程助手实测", "https://www.douyin.com/video/7234567891", "AI 编程助手", "ddg")],
    })
    with patch.dict(websearch._ENGINE_FUNCS, fake):
        items = douyin._search_via_site_search("AI 编程助手", 5)

    assert len(items) == 1
    assert "抖音 AI 编程助手实测" in items[0]["text"]
    assert "douyin.com/video" in items[0]["url"]
    normalize.normalize_douyin_items(items, "2026-01-01", "2026-12-31")


def test_toutiao_site_search_parses_dates_from_snippets():
    fake = _engines({
        "bing_cn": [SearchResult("头条 AI 编程助手评测", "https://www.toutiao.com/article/7234567890/", "AI 编程助手", "bing_cn", "2026-05-30")],
    })
    with patch.dict(websearch._ENGINE_FUNCS, fake):
        items = toutiao._search_via_site_search("AI 编程助手", 5)

    assert len(items) == 1
    assert items[0]["date"] == "2026-05-30"
    assert items[0]["source"] == "site-search:bing_cn"
    normalize.normalize_toutiao_items(items, "2026-01-01", "2026-12-31")


def test_xiaohongshu_is_always_attemptable():
    assert env.is_xiaohongshu_available({}) is True
