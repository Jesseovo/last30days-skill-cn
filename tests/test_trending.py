"""全网热榜（#16）: source parsing, RSS, cross-platform merge, rendering."""

import json
import os
import sys
from collections import OrderedDict
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from lib import trending  # noqa: E402


def _board(label, titles, kind="board"):
    return {
        "label": label,
        "code": label,
        "kind": kind,
        "items": [{"rank": i + 1, "title": t, "url": f"https://x.test/{label}/{i}"} for i, t in enumerate(titles)],
    }


# Titles captured from the live boards on 2026-10-03.
SNAPSHOT = OrderedDict([
    ("weibo", _board("微博热搜", ["爬珠峰的人都堵了", "巴勒斯坦球员向国足道歉", "中国队创亚运境外参赛金牌新纪录",
                               "中国队169金89银83铜收官", "EDGM战胜JDG", "郑钦文即时排名重返前50"])),
    ("baidu", _board("百度热搜", ["巴勒斯坦球员向国足道歉", "中国队169金89银83铜", "国庆长假自驾出行 怎么开才安全",
                               "中国男足时隔28年再夺亚运铜牌", "安东尼奥谈国足0比5惨败", "国足夺铜牌 安东尼奥抱起李昊欢呼"])),
    ("douyin", _board("抖音热榜", ["中国男足获亚运铜牌", "挑战0元搭车完成长途旅行", "中国队169金89银83铜收官", "国庆档观影repo"])),
    ("toutiao", _board("头条热榜", ["巴勒斯坦球员向国足致歉", "拿下点球大战！U23国足获亚运铜牌", "中国队亚运169金收官",
                                 "安东尼奥：此刻我是最幸福的教练", "小沈阳夫妇逆袭成国庆档票房黑马"])),
    ("bilibili", _board("B站热搜", ["上海EDG.M战胜北京JDG KPL", "亚运会国足夺铜牌"])),
    ("ithome", _board("IT之家", ["中国队169金89银83铜收官"], kind="feed")),
])


def _topics():
    return trending.merge_topics(SNAPSHOT)


def test_same_event_with_different_wording_is_merged():
    topics = _topics()
    medal = next(t for t in topics if "169" in t["title"])
    assert {m["platform"] for m in medal["mentions"]} == {"weibo", "baidu", "douyin", "toutiao"}
    bronze = next(t for t in topics if "铜牌" in t["title"] and "douyin" in {m["platform"] for m in t["mentions"]})
    assert {"baidu", "toutiao"} <= {m["platform"] for m in bronze["mentions"]}


def test_different_angles_are_not_chained_together():
    titles_by_topic = [{m["title"] for m in t["mentions"]} for t in _topics()]
    for titles in titles_by_topic:
        assert not ({"安东尼奥谈国足0比5惨败", "安东尼奥：此刻我是最幸福的教练"} <= titles)
        assert not ({"国庆档观影repo", "小沈阳夫妇逆袭成国庆档票房黑马"} <= titles)
    # medal tally and bronze match must stay separate events
    medal = next(t for t in _topics() if "169" in t["title"])
    assert not any("铜牌" in m["title"] for m in medal["mentions"])


def test_feeds_and_single_platform_items_are_not_topics():
    for topic in _topics():
        assert topic["platform_count"] >= 2
        assert all(m["platform"] != "ithome" for m in topic["mentions"])


def test_topics_sorted_by_platform_count_then_score():
    topics = _topics()
    keys = [(t["platform_count"], t["score"]) for t in topics]
    assert keys == sorted(keys, reverse=True)


def test_pinned_items_do_not_form_topics():
    boards = OrderedDict([
        ("weibo", {"label": "微博热搜", "kind": "board", "items": [{"rank": 1, "title": "置顶话题", "pinned": True}]}),
        ("baidu", {"label": "百度热搜", "kind": "board", "items": [{"rank": 1, "title": "置顶话题", "pinned": True}]}),
    ])
    assert trending.merge_topics(boards) == []


def test_parse_sources_groups_and_unknown(monkeypatch):
    monkeypatch.delenv("LAST30DAYS_HOT_SOURCES", raising=False)
    monkeypatch.delenv("LAST30DAYS_HOT_FEEDS", raising=False)
    assert trending.parse_sources(None) == list(trending.CN_BOARDS)
    assert trending.parse_sources("weibo,news")[:2] == ["weibo", "ithome"]
    assert "hackernews" in trending.parse_sources("all")
    with pytest.raises(trending.UnknownHotSource):
        trending.parse_sources("weibo,nope")


def test_custom_feeds_from_env(monkeypatch):
    monkeypatch.setenv("LAST30DAYS_HOT_FEEDS", "36氪快讯|https://rsshub.test/36kr/newsflashes,https://plain.test/rss")
    feeds = trending.custom_feeds()
    assert list(feeds.values()) == [("36氪快讯", "https://rsshub.test/36kr/newsflashes"), ("RSS2", "https://plain.test/rss")]
    assert "feed1" in trending.parse_sources(None)


RSS = """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0"><channel>
<item><title><![CDATA[旧文章]]></title><link>https://a.test/1</link><pubDate>Fri, 02 Oct 2026 08:00:00 +0800</pubDate></item>
<item><title>新文章</title><link>https://a.test/2</link><pubDate>Sat, 03 Oct 2026 11:21:48 GMT</pubDate></item>
</channel></rss>"""

ATOM = """<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Atom 条目</title>
<link href="https://b.test/1"/><updated>2026-10-03T09:00:00+08:00</updated></entry></feed>"""


def test_parse_rss_and_atom_feeds():
    rows = trending.parse_feed(RSS)
    assert [r["title"] for r in rows] == ["新文章", "旧文章"]
    assert rows[0]["published"] == "2026-10-03 19:21"
    atom = trending.parse_feed(ATOM)
    assert atom[0]["url"] == "https://b.test/1" and atom[0]["published"] == "2026-10-03 09:00"
    assert trending.parse_feed("not xml") == []


def test_filter_by_topic_keeps_matching_items():
    filtered = trending.filter_by_topic(SNAPSHOT, "国足")
    titles = [i["title"] for b in filtered.values() for i in b["items"]]
    assert "巴勒斯坦球员向国足道歉" in titles
    assert "爬珠峰的人都堵了" not in titles


def test_renderers_escape_and_link_safely():
    boards = OrderedDict([("weibo", _board("微博热搜", ["<script>alert(1)</script>"]))])
    boards["weibo"]["items"][0]["url"] = "javascript:alert(1)"
    data = {"generated_at": "2026-10-03 22:00", "timezone": "Asia/Shanghai", "topic_filter": "",
            "boards": boards, "topics": []}
    html = trending.render_html(data, site_title="热榜<b>")
    assert "<script>alert(1)</script>" not in html
    assert 'href="javascript:' not in html
    assert "热榜&lt;b&gt;" in html
    md = trending.render_markdown(data)
    assert md.startswith("🔥 last30days-cn")
    payload = trending.to_json(data)
    assert payload["boards"]["weibo"]["items"][0]["title"] == "<script>alert(1)</script>"


def test_fetch_all_isolates_failures():
    def ok(limit):
        return [{"rank": 1, "title": "热点", "url": "https://x.test"}]

    def boom(limit):
        raise RuntimeError("down")

    with patch.dict(trending.BOARDS, {"weibo": ("微博热搜", "WEIBO", ok), "baidu": ("百度热搜", "BAIDU", boom)}):
        result = trending.fetch_all(["weibo", "baidu"], limit=5, log=False)
    assert result["weibo"]["items"] and result["baidu"]["items"] == []
    assert "down" in result["baidu"]["error"]


def test_write_outputs(tmp_path):
    data = {"generated_at": "2026-10-03 22:00", "timezone": "Asia/Shanghai", "topic_filter": "",
            "boards": SNAPSHOT, "topics": _topics()}
    paths = trending.write_outputs(data, tmp_path, title="今日热点")
    assert json.loads((tmp_path / "hot.json").read_text(encoding="utf-8"))["topics"]
    assert "<h1>今日热点</h1>" in (tmp_path / "hot.html").read_text(encoding="utf-8")
    assert paths["md"].endswith("hot.md")
