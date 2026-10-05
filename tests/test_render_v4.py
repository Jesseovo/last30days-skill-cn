"""Registry-driven rendering (v4) and the v3 label bugs it fixes."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from lib import render, schema  # noqa: E402


def _report():
    return schema.create_report("AI编程助手", "2026-09-03", "2026-10-03", "all")


def test_xiaohongshu_collects_are_labelled_correctly():
    # v3 printed the share count as "收藏".
    eng = schema.Engagement(likes=10, collects=20, num_comments=3, shares=4)
    text = render.format_engagement("xiaohongshu", eng)
    assert "20收藏" in text and "4分享" in text


def test_zhihu_voteups_are_shown():
    # v3 read engagement.score, which the Zhihu normalizer never sets.
    assert "120赞同" in render.format_engagement("zhihu", schema.Engagement(voteups=120, num_comments=5))


def test_zero_and_missing_metrics_are_hidden():
    assert render.format_engagement("douyin", schema.Engagement(views=0, likes=None)) == ""
    assert render.format_engagement("douyin", None) == ""


def test_overseas_labels():
    assert render.format_engagement("hackernews", schema.Engagement(score=486, num_comments=284)) == " [486 points, 284评论]"
    assert render.format_engagement("github", schema.Engagement(stars=59000)) == " [★59,000]"


def test_compact_shows_wechat_account_and_toutiao_source():
    report = _report()
    report.wechat = [schema.WechatItem(id="WX1", title="文章", snippet="摘要", url="https://w.test",
                                       source_name="自落果", score=80, date="2026-09-21")]
    report.toutiao = [schema.ToutiaoItem(id="TT1", title="头条文章", abstract="摘要文字", url="https://t.test",
                                         source_name="新浪财经", score=70, date="2026-09-07")]
    output = render.render_compact(report)
    assert "**WX1** (得分:80) 自落果" in output
    assert "**TT1** (得分:70) 新浪财经" in output
    assert "摘要文字" in output


def test_multiline_bodies_are_collapsed():
    report = _report()
    report.bilibili = [schema.BilibiliItem(id="BL1", title="标题", url="https://b.test", bvid="BV1",
                                           channel_name="up", description="第一行\n第二行\n\n第三行", score=60)]
    output = render.render_compact(report)
    assert "第一行 第二行 第三行" in output


def test_global_section_and_status_footer():
    report = _report()
    report.hackernews = [schema.GlobalItem(id="HN1", platform="hackernews", title="Claude Code tips",
                                           url="https://news.ycombinator.com/item?id=1", author="pg",
                                           container="blog.test", score=88,
                                           engagement=schema.Engagement(score=100, num_comments=20))]
    report.weibo_error = "微博搜索现需登录"
    report.source_status = {
        "hackernews": {"state": "ok", "count": 1, "raw_count": 5, "elapsed": 1.2, "via": {"algolia": 5}},
        "weibo": {"state": "error", "count": 0, "raw_count": 0, "elapsed": 0.3, "via": {}},
        "zhihu": {"state": "empty", "count": 0, "raw_count": 4, "elapsed": 2.0, "via": {"site-search:ddg": 4}},
    }
    compact = render.render_compact(report)
    assert "### Hacker News 讨论" in compact
    assert "Hacker News · blog.test · @pg" in compact
    footer = render.render_source_status(report)
    assert "✅ Hacker News: 1 条（原始 5 条" in footer
    assert "❌ 微博: 微博搜索现需登录" in footer
    assert "⚠️ 知乎: 0 条" in footer


def test_fallback_only_sources_get_a_warning():
    report = _report()
    report.zhihu = [schema.ZhihuItem(id="ZH1", title="问题", excerpt="", url="https://www.zhihu.com/question/1",
                                     author="", score=50)]
    report.source_status = {"zhihu": {"state": "ok", "count": 1, "raw_count": 1, "via": {"site-search:ddg": 1}}}
    assert "公开搜索兜底" in render.render_compact(report)


def test_html_report_has_dark_mode_and_escapes_errors():
    report = _report()
    report.xiaohongshu_error = "<img src=x onerror=alert(1)> 需要登录"
    report.source_status = {"xiaohongshu": {"state": "error", "count": 0}}
    html = render.render_html_report(report)
    assert "prefers-color-scheme: dark" in html
    assert "<img src=x" not in html
    assert "XHS" in html


def test_full_report_includes_status_footer():
    report = _report()
    report.baidu = [schema.BaiduItem(id="BD1", title="百度结果", snippet="摘要", url="https://b.test",
                                     source_domain="CSDN博客", score=40, date="2026-09-21")]
    md = render.render_full_report(report)
    assert md.splitlines()[0].startswith("🌐 last30days-cn")
    assert "## 百度搜索结果" in md and "CSDN博客" in md and "**来源:**" in md


def test_context_snippet_lists_sources_with_links():
    report = _report()
    report.bilibili = [schema.BilibiliItem(id="BL1", title="视频", url="https://b.test/v", bvid="BV1",
                                           channel_name="up", score=90)]
    snippet = render.render_context_snippet(report)
    assert "[B站] 视频 — https://b.test/v" in snippet
