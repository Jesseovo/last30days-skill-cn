"""测试 WechatItem 无 engagement 属性时 render_compact 不崩溃。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from lib import schema, render
from lib.version import DISPLAY_VERSION


def test_render_compact_wechat_no_engagement():
    report = schema.create_report("test", "2026-01-01", "2026-01-31", "all")
    item = schema.WechatItem(
        id="WX1", title="测试文章", snippet="摘要",
        url="https://example.com", source_name="测试号",
        score=50, why_relevant="测试",
    )
    assert not hasattr(item, 'engagement')
    report.wechat = [item]
    output = render.render_compact(report)
    assert output.splitlines()[0] == f"🌐 last30days-cn v{DISPLAY_VERSION} · 数据截至 2026-01-31"
    assert "WX1" in output
    assert "测试文章" in output


def test_render_compact_badge_marks_cache_hit():
    report = schema.create_report("test", "2026-01-01", "2026-01-31", "all")
    report.from_cache = True
    output = render.render_compact(report)
    assert output.splitlines()[0].endswith("· 缓存")


def test_render_compact_wechat_empty_list():
    report = schema.create_report("test", "2026-01-01", "2026-01-31", "all")
    report.wechat = []
    output = render.render_compact(report)
    assert isinstance(output, str)
