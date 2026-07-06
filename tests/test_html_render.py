import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from lib import render, schema


def test_render_html_report_contains_guizang_style_sections():
    report = schema.create_report("AI 编程助手", "2026-05-01", "2026-05-31", "all")
    report.wechat = [
        schema.WechatItem(
            id="WX1",
            title="测试文章",
            snippet="这是一条测试摘要",
            url="https://example.com/a",
            source_name="测试公众号",
            date="2026-05-20",
            why_relevant="命中主题关键词",
            score=88,
        )
    ]

    html = render.render_html_report(report)

    assert "<!doctype html>" in html
    assert "GUIZANG SWISS REPORT" in html
    assert "AI 编程助手" in html
    assert "测试文章" in html
    assert "WECHAT" in html
    assert "#002FA7" in html


def test_write_outputs_creates_html_report(tmp_path):
    report = schema.create_report("测试主题", "2026-05-01", "2026-05-31", "all")
    report.baidu = [
        schema.BaiduItem(
            id="BD1",
            title="百度测试结果",
            snippet="测试摘要",
            url="https://example.com/b",
            source_domain="example.com",
            date="2026-05-21",
            why_relevant="相关",
            score=77,
        )
    ]

    old_output_dir = render.OUTPUT_DIR
    old_env = os.environ.get("LAST30DAYS_OUTPUT_DIR")
    os.environ["LAST30DAYS_OUTPUT_DIR"] = str(tmp_path)
    try:
        render.write_outputs(report)
        html_path = Path(render.get_html_path())
        assert html_path.exists()
        assert html_path.read_text(encoding="utf-8").startswith("<!doctype html>")
    finally:
        render.OUTPUT_DIR = old_output_dir
        if old_env is None:
            os.environ.pop("LAST30DAYS_OUTPUT_DIR", None)
        else:
            os.environ["LAST30DAYS_OUTPUT_DIR"] = old_env


def test_collect_ranked_items_gives_relevant_small_sources_a_floor():
    report = schema.create_report("AI 编程助手", "2026-05-01", "2026-05-31", "all")
    report.weibo = [
        schema.WeiboItem(id=f"WB{i}", text=f"微博{i}", url="", author_handle=f"a{i}", score=90, relevance=0.9)
        for i in range(40)
    ]
    report.zhihu = [
        schema.ZhihuItem(id=f"ZH{i}", title=f"知乎{i}", excerpt="", url="", author=f"z{i}", score=50, relevance=0.5)
        for i in range(2)
    ]

    ranked = render._collect_ranked_items(report, limit=30)
    ranked_ids = {item.id for _, item in ranked}
    assert {"ZH0", "ZH1"} <= ranked_ids


def test_collect_ranked_items_does_not_floor_low_relevance_sources():
    report = schema.create_report("AI 编程助手", "2026-05-01", "2026-05-31", "all")
    report.weibo = [
        schema.WeiboItem(id=f"WB{i}", text=f"微博{i}", url="", author_handle=f"a{i}", score=90, relevance=0.9)
        for i in range(40)
    ]
    report.zhihu = [
        schema.ZhihuItem(id=f"ZH{i}", title=f"知乎{i}", excerpt="", url="", author=f"z{i}", score=50, relevance=0.05)
        for i in range(2)
    ]

    ranked = render._collect_ranked_items(report, limit=30)
    ranked_ids = {item.id for _, item in ranked}
    assert "ZH0" not in ranked_ids
