"""Source registry, source selection and the parallel pipeline (v4)."""

import os
import sys
import time
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import last30days  # noqa: E402
from lib import pipeline, schema, sources  # noqa: E402


# --- registry -----------------------------------------------------------------

def test_registry_has_eight_cn_sources_in_canonical_order():
    assert sources.CN_SOURCE_IDS == (
        "weibo", "xiaohongshu", "bilibili", "zhihu", "douyin", "wechat", "baidu", "toutiao",
    )
    assert set(sources.NATIVE_GLOBAL_IDS) == {"hackernews", "github", "reddit"}


def test_parse_list_handles_aliases_groups_and_upstream_platforms():
    ids, upstream = sources.parse_list("xhs, B站, hn,youtube")
    assert ids == {"xiaohongshu", "bilibili", "hackernews", "upstream"}
    assert upstream == {"youtube"}
    assert sources.parse_list("global")[0] == set(sources.NATIVE_GLOBAL_IDS)
    assert sources.parse_list("cn")[0] == set(sources.CN_SOURCE_IDS)
    with pytest.raises(sources.UnknownSourceError):
        sources.parse_list("weibo,myspace")


@pytest.mark.parametrize("item_id,expected", [
    ("XHS3", "xiaohongshu"), ("WB12", "weibo"), ("BL1", "bilibili"), ("HN2", "hackernews"),
    ("GH10", "github"), ("UP1", "upstream"), ("TT7", "toutiao"), ("XHSX", None), ("ZZ1", None),
])
def test_item_id_prefix_lookup(item_id, expected):
    assert sources.source_for_item_id(item_id) == expected


# --- CLI source resolution -------------------------------------------------------

@pytest.fixture
def clean_env(monkeypatch):
    for key in ("LAST30DAYS_DEFAULT_SEARCH", "EXCLUDE_SOURCES", "INCLUDE_SOURCES"):
        monkeypatch.delenv(key, raising=False)
    return monkeypatch


def test_global_flag_adds_native_overseas_sources(clean_env):
    assert last30days.resolve_search_sources(None, include_global=True) == (
        last30days.ALL_SOURCE_IDS | set(sources.NATIVE_GLOBAL_IDS)
    )


def test_include_sources_env_adds_to_default(clean_env):
    clean_env.setenv("INCLUDE_SOURCES", "hn")
    assert last30days.resolve_search_sources(None) == last30days.ALL_SOURCE_IDS | {"hackernews"}


def test_include_then_exclude(clean_env):
    clean_env.setenv("INCLUDE_SOURCES", "global")
    clean_env.setenv("EXCLUDE_SOURCES", "reddit,douyin")
    result = last30days.resolve_search_sources(None)
    assert "reddit" not in result and "douyin" not in result and "github" in result


def test_unknown_search_token_exits(clean_env, capsys):
    with pytest.raises(SystemExit):
        last30days.parse_search_flag("weibo,unknown")
    assert "未知搜索源" in capsys.readouterr().err


def test_upstream_platforms_are_collected(clean_env):
    assert last30days._upstream_platforms("x,youtube,weibo") == ["x", "youtube"]


def test_select_sources_defaults_to_all_cn_and_quick_uses_tiers():
    assert pipeline.select_sources(None, "breaking_news", "default") == list(sources.CN_SOURCE_IDS)
    quick = pipeline.select_sources(None, "breaking_news", "quick")
    assert set(quick) < set(sources.CN_SOURCE_IDS) and "weibo" in quick
    assert pipeline.select_sources({"github", "weibo"}, "concept", "default") == ["weibo", "github"]


# --- pipeline -------------------------------------------------------------------

def _ctx(**kwargs):
    base = dict(topic="AI编程助手", search_topic="AI编程助手", from_date="2026-09-03", to_date="2026-10-03")
    base.update(kwargs)
    return pipeline.RunContext(**base)


def test_run_sources_isolates_errors_and_enforces_deadlines():
    def good(ctx):
        return [{"title": "AI编程助手 评测", "url": "https://x.test/1", "source": "api"}]

    def broken(ctx):
        raise RuntimeError("boom")

    def slow(ctx):
        time.sleep(1.5)
        return [{"title": "late"}]

    timeouts = {"future": 1, "bilibili_future": 5, "zhihu_future": 5, "douyin_future": 0.2}
    with patch.dict(pipeline.SEARCHERS, {"bilibili": good, "zhihu": broken, "douyin": slow}):
        started = time.monotonic()
        results = pipeline.run_sources(_ctx(), ["bilibili", "zhihu", "douyin"], timeouts, log=False)
        elapsed = time.monotonic() - started
    assert elapsed < 1.4  # did not wait for the slow source
    assert results["bilibili"]["state"] == "ok" and results["bilibili"]["via"] == {"api": 1}
    assert results["zhihu"]["state"] == "error" and "boom" in results["zhihu"]["error"]
    assert results["douyin"]["state"] == "timeout" and "超时" in results["douyin"]["error"]


def test_overseas_sources_require_an_english_query():
    results = pipeline.run_sources(_ctx(overseas_query=None), ["hackernews"], log=False)
    assert results["hackernews"]["state"] == "error"
    assert "--global-query" in results["hackernews"]["error"]


def test_process_and_build_report_records_status():
    raw = {
        "bilibili": {
            "items": [
                {"id": "BL1", "title": "AI编程助手 新功能", "url": "https://b.test/1", "bvid": "BV1",
                 "channel_name": "up", "date": "2026-09-20", "relevance": 0.9,
                 "engagement": {"views": 100}, "source": "wbi-search"},
                {"id": "BL2", "title": "AI编程助手 旧视频", "url": "https://b.test/2", "bvid": "BV2",
                 "channel_name": "up2", "date": "2025-01-01", "relevance": 0.9, "source": "wbi-search"},
            ],
            "error": None, "state": "ok", "elapsed": 1.2, "via": {"wbi-search": 2},
        },
        "weibo": {"items": [], "error": "微博搜索现需登录", "state": "error", "elapsed": 0.3, "via": {}},
    }
    processed = pipeline.process_results(raw, "2026-09-03", "2026-10-03", "breaking_news")
    assert [i.id for i in processed["bilibili"]] == ["BL1"]  # out-of-window item dropped
    report = pipeline.build_report("AI编程助手", _ctx(), raw, processed, "breaking_news")
    assert report.source_status["bilibili"]["raw_count"] == 2
    assert report.source_status["bilibili"]["count"] == 1
    assert report.weibo_error == "微博搜索现需登录"
    assert report.query_type == "breaking_news"
    restored = schema.Report.from_dict(report.to_dict())
    assert restored.source_status == report.source_status
    assert restored.bilibili[0].bvid == "BV1"


def test_query_terms_alone_do_not_make_a_cross_platform_cluster():
    raw = {
        "bilibili": {"items": [{"id": "BL1", "title": "AI编程助手", "url": "https://b.test/1", "bvid": "BV1",
                                "channel_name": "a", "date": "2026-09-20", "relevance": 1.0}],
                     "error": None, "state": "ok", "via": {}},
        "toutiao": {"items": [{"id": "TT1", "title": "开拓者AI编程助手 重磅发布！", "url": "https://t.test/1",
                               "source_name": "新浪财经", "date": "2026-09-20", "relevance": 1.0}],
                    "error": None, "state": "ok", "via": {}},
    }
    processed = pipeline.process_results(raw, "2026-09-03", "2026-10-03", "breaking_news")
    report = pipeline.build_report("AI编程助手", _ctx(), raw, processed, "breaking_news")
    assert report.clusters == []
    assert report.bilibili[0].cross_refs == []
