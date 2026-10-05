"""v4 platform parsers, built from structures observed on live pages (2026-10)."""

import json
import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from lib import baidu, douyin, http, toutiao, wechat, weibo, xiaohongshu  # noqa: E402

# --- 微信（搜狗）-----------------------------------------------------------

SOGOU_HTML = """
<div class="header"><a href="http://pic.sogou.com/pics?query=x">图片</a><a href="http://zhihu.sogou.com/zhihu?query=x">知乎</a></div>
<ul class="news-list">
  <li id="sogou_vr_11002601_box_0">
    <div class="txt-box">
      <h3><a target="_blank" href="/link?url=dn9a_abc&amp;type=2&amp;query=AI">你的<em><!--red_beg-->AI编程助手<!--red_end--></em>,可能正在偷你的代码</a></h3>
      <p class="txt-info">新一代AI编程助手要理解整个项目架构&hellip;</p>
      <div class="s-p"><span class="all-time-y2">自落果</span><span class="s2"><script>document.write(timeConvert('1790000000'))</script></span></div>
    </div>
  </li>
  <li id="sogou_vr_11002601_box_1">
    <div class="txt-box">
      <h3><a href="/link?url=second">第二篇文章</a></h3>
      <div class="s-p"><span class="all-time-y2">IT信差</span></div>
    </div>
  </li>
</ul>
<div class="footer"><a href="https://www.sogou.com/web?m2web=mingyi.sogou.com">医疗</a></div>
"""


def test_sogou_parser_ignores_navigation_links():
    items = wechat.parse_sogou_html(SOGOU_HTML)
    assert [i["title"] for i in items] == ["你的AI编程助手,可能正在偷你的代码", "第二篇文章"]
    first = items[0]
    assert first["url"] == "https://weixin.sogou.com/link?url=dn9a_abc&type=2&query=AI"
    assert first["source_name"] == "自落果"
    assert first["date"] == "2026-09-21"
    assert first["snippet"].endswith("…")
    assert items[1]["date"] is None
    assert all("pic.sogou.com" not in i["url"] and "mingyi" not in i["url"] for i in items)


def test_sogou_antispider_raises_clear_error():
    with patch.object(http, "fetch", return_value=(200, "https://weixin.sogou.com/antispider/?from=x", "")):
        with pytest.raises(http.HTTPError) as exc:
            wechat._search_via_sogou("AI")
    assert "antispider" in str(exc.value)


# --- 头条（so.toutiao.com SSR）----------------------------------------------

def _card(data):
    return f'<script data-druid-card-data-id="x" type="application/json" nonce="n">{json.dumps({"data": data}, ensure_ascii=False)}</script>'


TOUTIAO_HTML = "<html><body>" + _card({
    "title": "开拓者<em>AI编程助手</em> 重磅发布！", "group_id": "7682701133227344384",
    "info": {"url": "https://www.toutiao.com/group/7682701133227344384/"},
    "article_url": "http://finance.sina.com.cn/wm/2026-09-07/doc.shtml",
    "datetime": "2026-09-07 16:04:17", "source": "新浪财经",
    "comment_count": 2, "read_count": 52, "digg_count": 3,
    "summary": {"text": "来源：市场资讯"},
}) + _card({"cell_type": 1}) + "</body></html>"


def test_toutiao_ssr_cards_are_parsed():
    items = toutiao.parse_so_html(TOUTIAO_HTML)
    assert len(items) == 1
    item = items[0]
    assert item["title"] == "开拓者AI编程助手 重磅发布！"
    assert item["url"] == "https://www.toutiao.com/group/7682701133227344384/"
    assert item["original_url"].startswith("http://finance.sina.com.cn")
    assert item["date"] == "2026-09-07"
    assert item["source_name"] == "新浪财经"
    assert item["engagement"] == {"comments": 2, "likes": 3, "reads": 52}
    assert item["abstract"] == "来源：市场资讯"


def test_toutiao_retries_empty_shell_pages():
    shell = (200, "https://so.toutiao.com/search?keyword=x", "<html><script>var druid={}</script></html>")
    full = (200, "https://so.toutiao.com/search?keyword=x", TOUTIAO_HTML)
    with patch.object(http, "fetch", side_effect=[shell, full]), patch("lib.toutiao.time.sleep"):
        items = toutiao._search_via_so("AI编程助手")
    assert len(items) == 1


def test_toutiao_hot_board_strips_tracking_query():
    payload = {"data": [{"Title": "热点", "Url": "https://www.toutiao.com/trending/769/?log_pb=%7B%7D&rank=1", "HotValue": "123"}]}
    with patch.object(http, "get", return_value=payload):
        hot = toutiao.fetch_hot(5)
    assert hot[0]["url"] == "https://www.toutiao.com/trending/769/"
    assert hot[0]["hot_value"] == 123


# --- 微博 ------------------------------------------------------------------

def test_weibo_login_wall_is_detected():
    class Session:
        headers = {}

        def get_json(self, url, **kwargs):
            return {"ok": -100, "url": "https://passport.weibo.com/sso/signin?entry=wapsso"}

    with patch.object(weibo, "_mobile_session", return_value=Session()):
        with pytest.raises(weibo.WeiboLoginRequired):
            weibo._search_via_mobile("AI", 1, cookie=None)


def test_weibo_search_explains_login_requirement_when_everything_fails():
    with patch.object(weibo, "_search_via_mobile", side_effect=weibo.WeiboLoginRequired()), \
            patch.object(weibo, "fetch_hot", return_value=[]), \
            patch.object(weibo, "_search_via_site_search", return_value=[]), \
            patch("lib.crawler_bridge.is_playwright_available", return_value=False):
        with pytest.raises(http.HTTPError) as exc:
            weibo.search_weibo("AI编程助手", "2026-09-03", "2026-10-03", depth="quick")
    assert "login weibo" in str(exc.value) and "WEIBO_COOKIE" in str(exc.value)


def test_weibo_hot_search_parsing_and_topic_match():
    payload = {"data": {"realtime": [
        {"word": "AI面试被指不尊重人", "num": 1163453, "label_name": "新", "realpos": 5, "word_scheme": "#AI面试被指不尊重人#"},
        {"word": "广告位", "is_ad": 1},
    ]}}
    with patch.object(http, "get", return_value=payload):
        hot = weibo.fetch_hot(10)
        matched = weibo._search_hot_related("AI面试")
    assert len(hot) == 1 and hot[0]["rank"] == 5 and hot[0]["label"] == "新"
    assert "s.weibo.com/weibo?q=%23" in hot[0]["url"]
    assert matched and matched[0]["source"] == "hot-search" and "热搜第 5 位" in matched[0]["why_relevant"]


def test_weibo_mobile_cards_and_dates():
    payload = {"data": {"cards": [
        {"card_type": 9, "mblog": {"text": "<a>#话题#</a> 正文", "mid": "1", "bid": "Abc123",
                                   "user": {"id": 7, "screen_name": "作者"}, "created_at": "Tue Sep 22 10:00:00 +0800 2026",
                                   "reposts_count": 1, "comments_count": "2", "attitudes_count": "1.5万"}},
        {"card_type": 11, "card_group": [{"mblog": {"text": "二", "id": "2", "user": {"id": 8}, "created_at": "刚刚"}}]},
    ]}}
    items = weibo.parse_mobile_cards(payload)
    assert len(items) == 2
    assert items[0]["url"] == "https://weibo.com/7/Abc123"
    assert items[0]["date"] == "2026-09-22"
    assert items[0]["engagement"] == {"reposts": 1, "comments": 2, "likes": 15000}
    assert items[1]["date"] is not None


def test_weibo_month_day_dates_roll_back_a_year_when_in_future():
    from datetime import datetime
    from lib import dates
    now = datetime.now(dates.CST)
    future = (now.month % 12) + 1
    parsed = weibo._parse_weibo_date(f"{future:02d}-01")
    expected_year = now.year if future <= now.month else now.year - 1
    if future == 1 and now.month == 12:
        expected_year = now.year
    assert parsed.startswith(str(expected_year))


# --- 小红书 ----------------------------------------------------------------

MCP_FEED = {
    "id": "65a1b2c3d4e5f60718293a4b", "xsecToken": "ABxyz==",
    "noteCard": {"displayTitle": "AI 编程助手 #效率#", "user": {"nickname": "小红薯"},
                 "interactInfo": {"likedCount": "1.2万", "collectedCount": "300", "commentCount": "10+", "sharedCount": 5},
                 "time": 1790000000000},
}


def test_xhs_mcp_feed_parsing_with_xsec_token():
    parsed = xiaohongshu.parse_mcp_feed(MCP_FEED)
    assert parsed["url"] == ("https://www.xiaohongshu.com/explore/65a1b2c3d4e5f60718293a4b"
                             "?xsec_token=ABxyz%3D%3D&xsec_source=pc_search")
    assert parsed["engagement"] == {"likes": 12000, "collects": 300, "comments": 10, "shares": 5}
    assert parsed["date"] == "2026-09-21"
    assert parsed["hashtags"] == ["效率"]


def test_xhs_mcp_uses_feeds_search_post_contract():
    calls = {}

    def fake_get(url, **kwargs):
        return {"data": {"is_logged_in": True}}

    def fake_post(url, payload, **kwargs):
        calls["url"] = url
        calls["payload"] = payload
        return {"data": {"feeds": [MCP_FEED]}}

    with patch.object(http, "get", side_effect=fake_get), patch.object(http, "post", side_effect=fake_post):
        items = xiaohongshu._search_via_mcp("AI 编程助手", "default", 20, "http://127.0.0.1:18060/")
    assert calls["url"] == "http://127.0.0.1:18060/api/v1/feeds/search"
    assert calls["payload"]["keyword"] == "AI 编程助手"
    assert len(items) == 1


def test_xhs_reports_login_hint_when_all_paths_fail():
    with patch("lib.crawler_bridge.is_playwright_available", return_value=False), \
            patch.object(xiaohongshu, "_search_via_site_search", return_value=[]):
        with pytest.raises(http.HTTPError) as exc:
            xiaohongshu.search_xiaohongshu("AI", "2026-09-03", "2026-10-03")
    assert "login xiaohongshu" in str(exc.value)


def test_xhs_parse_count_variants():
    assert xiaohongshu.parse_count("1.2万") == 12000
    assert xiaohongshu.parse_count("3亿") == 300000000
    assert xiaohongshu.parse_count("10+") == 10
    assert xiaohongshu.parse_count("") == 0
    assert xiaohongshu.parse_count(None) == 0


# --- 抖音 ------------------------------------------------------------------

def test_douyin_parse_aweme_dates_and_duration():
    aweme = {"aweme_id": "7234", "desc": "AI 编程 #效率", "create_time": 1790000000,
             "author": {"nickname": "作者", "uid": 9}, "statistics": {"play_count": 10, "digg_count": 2},
             "text_extra": [{"hashtag_name": "效率"}], "video": {"duration": 15230}}
    parsed = douyin.parse_aweme(aweme)
    assert parsed["url"] == "https://www.douyin.com/video/7234"
    assert parsed["date"] == "2026-09-21"
    assert parsed["duration"] == 15
    assert parsed["hashtags"] == ["效率"]


def test_douyin_hot_list_parsing():
    payload = {"data": {"word_list": [{"word": "中国男足获亚运铜牌", "hot_value": 11596271, "position": 1, "sentence_id": "2679413"}]}}
    with patch.object(http, "get", return_value=payload):
        hot = douyin.fetch_hot(10)
    assert hot == [{"rank": 1, "title": "中国男足获亚运铜牌", "url": "https://www.douyin.com/hot/2679413",
                    "hot_value": 11596271, "label": "", "event_time": None}]


def test_douyin_failure_message_mentions_fixes():
    with patch("lib.crawler_bridge.is_playwright_available", return_value=False), \
            patch.object(douyin, "_search_hot_related", return_value=[]), \
            patch.object(douyin, "_search_via_site_search", return_value=[]):
        with pytest.raises(http.HTTPError) as exc:
            douyin.search_douyin("AI", "2026-09-03", "2026-10-03")
    assert "TIKHUB_API_KEY" in str(exc.value) and "login douyin" in str(exc.value)


# --- 百度 ------------------------------------------------------------------

BAIDU_HTML = """
<div class="result-op c-container new-pmd" tpl="sg_kg_entity_san" mu="https://baike.baidu.com/item/x">
  <h3><a href="https://baike.baidu.com/item/x">百科卡片</a></h3></div>
<div class="result-op c-container new-pmd" tpl="ai_ecology" mu="http://nourl.ubs.baidu.com/aiapp-1"><h3><a href="#">AI 应用</a></h3></div>
<div class="result c-container xpath-log new-pmd" tpl="www_index" mu="https://blog.csdn.net/a/article/details/1?x=1&amp;y=2">
  <h3 class="t"><a href="http://www.baidu.com/link?url=abc">2026年<em>AI编程</em>工具实战</a></h3>
  <span class="cos-space-mr-3xs prefix-time_650Xx">2026年9月21日</span>
  <span class="summary-text_15QGa">1.1 <em>AI编程</em>工具的三种不同形态</span></div>
  <span class="cosc-source-text cos-line-clamp-1">CSDN博客</span>
</div>
<div class="result c-container new-pmd" data-tuiguang="1" mu="https://ad.test/"><h3><a href="https://ad.test/">广告</a></h3></div>
"""


def test_baidu_parser_skips_cards_ads_and_extracts_fields():
    items = baidu.parse_baidu_html(BAIDU_HTML)
    assert len(items) == 1
    item = items[0]
    assert item["url"] == "https://blog.csdn.net/a/article/details/1?x=1&y=2"
    assert item["title"] == "2026年AI编程工具实战"
    assert item["date"] == "2026-09-21"
    assert item["source_domain"] == "CSDN博客"
    assert item["snippet"].startswith("1.1 AI编程工具")
    assert item["source"] == "baidu-web"


def test_baidu_qianfan_references_are_parsed():
    payload = {"references": [
        {"id": 1, "title": "<b>标题</b>", "url": "https://news.test/a", "content": "内容", "date": "2026-09-30 10:00:00", "website": "新闻网"},
        {"id": 2, "title": "", "url": "https://skip.test"},
    ]}
    items = baidu.parse_api_references(payload)
    assert len(items) == 1
    assert items[0]["title"] == "标题" and items[0]["date"] == "2026-09-30"
    assert items[0]["source_domain"] == "新闻网" and items[0]["source"] == "qianfan-api"


def test_baidu_recency_filter_mapping():
    assert baidu._recency_filter("2026-09-26", "2026-10-03") == "week"
    assert baidu._recency_filter("2026-09-03", "2026-10-03") == "month"
    assert baidu._recency_filter("2026-01-01", "2026-10-03") == "year"


def test_baidu_hot_board_from_s_data():
    data = {"data": {"cards": [{"content": [
        {"word": "置顶话题", "hotScore": "7904077", "isTop": True, "rawUrl": "https://www.baidu.com/s?wd=a"},
        {"word": "巴勒斯坦球员向国足道歉", "hotScore": "7807888", "hotTag": "3", "rawUrl": "https://www.baidu.com/s?wd=b", "desc": "描述"},
    ]}]}}
    html = f"<html><!--s-data:{json.dumps(data, ensure_ascii=False)}--></html>"
    with patch.object(http, "get_text", return_value=html):
        hot = baidu.fetch_hot(10)
    assert hot[0]["label"] == "置顶" and hot[0]["pinned"] is True
    assert hot[1]["label"] == "热" and hot[1]["hot_value"] == 7807888 and hot[1]["rank"] == 2
