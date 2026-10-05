"""Multi-engine web-search fallback: parsing, unwrapping, validation, blocking."""

import base64
import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from lib import websearch  # noqa: E402
from lib.websearch import SearchResult  # noqa: E402


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    websearch.reset_state()
    monkeypatch.setattr(websearch, "MIN_INTERVAL_SECONDS", 0)
    monkeypatch.delenv("LAST30DAYS_WEBSEARCH_ENGINES", raising=False)
    yield
    websearch.reset_state()


def _bing_href(target: str) -> str:
    encoded = base64.urlsafe_b64encode(target.encode()).decode().rstrip("=")
    return f"https://www.bing.com/ck/a?!&amp;&amp;p=abc&amp;u=a1{encoded}&amp;ntb=1"


BING_HTML = f"""
<ol id="b_results">
<li class="b_algo" data-id="1">
  <div class="b_tpcn"><a class="tilk" href="{_bing_href('https://www.zhihu.com/question/123')}">zhihu.com</a></div>
  <h2 class=""><a target="_blank" href="{_bing_href('https://www.zhihu.com/question/123')}"><strong>AI</strong> 编程助手怎么选？</a></h2>
  <div class="b_caption"><p class="b_lineclamp2"><span class="news_dt">2026年9月21日</span>&nbsp;&#0183;&#32;横评 Claude Code 与 Cursor …</p></div>
</li>
<li class="b_algo">
  <h2><a href="https://example.com/plain">Plain result</a></h2>
  <p>no caption wrapper</p>
</li>
</ol>
"""

DDG_HTML = """
<div class="result results_links">
  <a rel="nofollow" class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.xiaohongshu.com%2Fexplore%2F65a1b2c3d4e5f60718293a4b&amp;rut=1">AI 编程助手测评 - 小红书</a>
  <a class="result__snippet" href="#">2026-09-03 实测五款 AI 编程助手</a>
</div>
"""


def test_unwrap_bing_redirect_links():
    assert websearch.unwrap_bing_url(_bing_href("https://a.test/x?y=1")) == "https://a.test/x?y=1"
    assert websearch.unwrap_bing_url("https://plain.test/") == "https://plain.test/"


def test_parse_bing_html_extracts_title_url_snippet_and_date():
    results = websearch.parse_bing_html(BING_HTML, engine="bing_cn")
    assert len(results) == 2
    first = results[0]
    assert first.url == "https://www.zhihu.com/question/123"
    assert first.title == "AI 编程助手怎么选？"
    assert first.date == "2026-09-21"
    assert "横评" in first.snippet
    assert results[1].url == "https://example.com/plain"


def test_parse_ddg_html_unwraps_uddg_links():
    results = websearch.parse_ddg_html(DDG_HTML)
    assert len(results) == 1
    assert results[0].url == "https://www.xiaohongshu.com/explore/65a1b2c3d4e5f60718293a4b"
    assert results[0].date == "2026-09-03"


def test_extract_date_only_reads_leading_dates():
    assert websearch.extract_date("2026年5月30日 · 正文") == "2026-05-30"
    assert websearch.extract_date("正文" + "很长" * 25 + " 2026-05-30") is None
    assert websearch.extract_date("2026年13月30日") is None


def _fake_engines(table):
    def make(name):
        def run(query, timeout):
            value = table.get(name, [])
            if isinstance(value, Exception):
                raise value
            return value
        return run
    return {name: make(name) for name in ("bing_cn", "ddg", "bing")}


def test_search_validates_url_pattern_and_relevance():
    table = {
        "bing_cn": [
            SearchResult("活动地图", "https://www.zhihu.com/question/1", "体育赛事", "bing_cn"),  # decoy
            SearchResult("AI 编程助手推荐", "https://www.zhihu.com/question/2", "", "bing_cn"),
            SearchResult("AI 编程助手推荐", "https://other.test/2", "", "bing_cn"),  # wrong site
        ],
    }
    with patch.dict(websearch._ENGINE_FUNCS, _fake_engines(table)):
        results = websearch.search("site:zhihu.com AI 编程助手", topic="AI 编程助手",
                                   url_pattern=r"zhihu\.com/question/\d+")
    assert [r.url for r in results] == ["https://www.zhihu.com/question/2"]


def test_blocked_engine_is_remembered_and_skipped():
    calls = []

    def blocked(query, timeout):
        calls.append(query)
        raise websearch.EngineBlocked("homepage")

    engines = _fake_engines({"ddg": [SearchResult("AI 编程助手", "https://x.test/1", "", "ddg")]})
    engines["bing_cn"] = blocked
    with patch.dict(websearch._ENGINE_FUNCS, engines):
        websearch.search("AI 编程助手", topic="AI 编程助手")
        websearch.search("AI 编程助手", topic="AI 编程助手")
    assert len(calls) == 1
    assert "bing_cn" in websearch.blocked_engines()
    assert "cn.bing.com" in websearch.describe_failure("知乎")


def test_stops_after_first_engine_with_validated_hits():
    hit = SearchResult("AI 编程助手", "https://x.test/1", "", "bing_cn")
    called = []

    def ddg(query, timeout):
        called.append("ddg")
        return []

    engines = _fake_engines({"bing_cn": [hit]})
    engines["ddg"] = ddg
    with patch.dict(websearch._ENGINE_FUNCS, engines):
        assert websearch.search("AI 编程助手", topic="AI 编程助手") == [hit]
    assert called == []


def test_engine_order_can_be_configured(monkeypatch):
    monkeypatch.setenv("LAST30DAYS_WEBSEARCH_ENGINES", "ddg,unknown,bing")
    assert websearch.configured_engines() == ["ddg", "bing"]


def test_bing_homepage_redirect_is_detected():
    assert websearch._is_bing_homepage("https://www.bing.com/?q=x", "<div class=\"hp_body\"></div>")
    assert not websearch._is_bing_homepage("https://www.bing.com/search?q=x", '<li class="b_algo">')
