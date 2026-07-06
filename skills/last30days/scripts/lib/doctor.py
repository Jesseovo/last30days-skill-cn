"""Human-readable source diagnostics for last30days-cn."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List

from . import crawler_bridge, env


@dataclass
class SourceRecord:
    source: str
    label: str
    status: str
    available: bool
    reason: str
    fix: str = ""
    fix_cli: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _record(
    source: str,
    label: str,
    status: str,
    available: bool,
    reason: str,
    fix: str = "",
    fix_cli: str = "",
) -> SourceRecord:
    return SourceRecord(source, label, status, available, reason, fix, fix_cli)


def build_report(config: Dict[str, Any]) -> Dict[str, Any]:
    """Build a source-by-source diagnostic report."""
    crawler_status = crawler_bridge.get_crawler_status()
    has_playwright = bool(crawler_status.get("playwright_available"))

    records: List[SourceRecord] = []

    weibo_ok = env.is_weibo_available(config)
    records.append(_record(
        "weibo",
        "微博",
        "ok" if weibo_ok else "warn",
        weibo_ok,
        "已配置 API token 或 Playwright 可用" if weibo_ok else "未配置微博 API，且 Playwright 不可用；仍会尝试移动端公开接口",
        "安装 Playwright 或配置 WEIBO_ACCESS_TOKEN 可提高稳定性",
        "python -m pip install playwright && python -m playwright install chromium",
    ))

    xhs_ok = env.is_xiaohongshu_available(config)
    records.append(_record(
        "xiaohongshu",
        "小红书",
        "ok" if xhs_ok else "warn",
        xhs_ok,
        "MCP/Playwright/公开搜索至少一条路径可尝试" if xhs_ok else "MCP 与 Playwright 均不可用，仅剩公开搜索兜底",
        "推荐安装 Playwright 并登录小红书",
        "python -m pip install playwright && python -m playwright install chromium",
    ))

    bilibili_ok = env.probe_bilibili()
    records.append(_record(
        "bilibili",
        "B站",
        "ok" if bilibili_ok else ("warn" if has_playwright else "error"),
        bilibili_ok or has_playwright,
        "公开搜索 API 可用" if bilibili_ok else "公开搜索 API 探测失败" + ("；可尝试 Playwright 兜底" if has_playwright else "；且 Playwright 不可用"),
        "安装 Playwright 作为备用抓取路径",
        "python -m pip install playwright && python -m playwright install chromium",
    ))

    zhihu_ok = env.probe_zhihu()
    records.append(_record(
        "zhihu",
        "知乎",
        "ok" if zhihu_ok else ("warn" if has_playwright else "error"),
        zhihu_ok or has_playwright,
        "公开搜索 API 可用" if zhihu_ok else "知乎公开 API 探测失败" + ("；可尝试 Playwright 兜底" if has_playwright else "；且 Playwright 不可用"),
        "配置 ZHIHU_COOKIE 或安装 Playwright 可提高稳定性",
        "python -m pip install playwright && python -m playwright install chromium",
    ))

    douyin_ok = env.is_douyin_available(config)
    records.append(_record(
        "douyin",
        "抖音",
        "ok" if douyin_ok else "warn",
        douyin_ok,
        "已配置 TikHub/抖音 API 或 Playwright 可用" if douyin_ok else "未配置 API 且 Playwright 不可用；会尝试公开接口/搜索兜底",
        "配置 TIKHUB_API_KEY 或安装 Playwright",
        "python -m pip install playwright && python -m playwright install chromium",
    ))

    wechat_ok = env.is_wechat_available(config)
    records.append(_record(
        "wechat",
        "微信公众号",
        "ok" if wechat_ok else "warn",
        wechat_ok,
        "已配置 WECHAT_API_KEY" if wechat_ok else "未配置 WECHAT_API_KEY；会尝试搜狗微信公开搜索",
        "配置 WECHAT_API_KEY 可提高稳定性",
        "echo WECHAT_API_KEY=your_key >> ~/.config/last30days-cn/.env",
    ))

    baidu_api_ok = env.is_baidu_api_available(config)
    records.append(_record(
        "baidu",
        "百度",
        "ok" if baidu_api_ok else "warn",
        True,
        "已配置百度 API" if baidu_api_ok else "未配置百度 API；会使用公开搜索兜底",
        "配置 BAIDU_API_KEY 与 BAIDU_SECRET_KEY 可提升稳定性",
        "echo BAIDU_API_KEY=your_key >> ~/.config/last30days-cn/.env",
    ))

    toutiao_ok = env.probe_toutiao()
    records.append(_record(
        "toutiao",
        "今日头条",
        "ok" if toutiao_ok else "warn",
        True,
        "头条原生搜索接口可用" if toutiao_ok else "头条原生接口可能被签名/风控限制；会使用公开搜索兜底",
        "无必须配置；若结果稀疏，请尝试 --search toutiao,baidu 交叉验证",
        "python scripts/last30days.py \"你的主题\" --search toutiao,baidu",
    ))

    summary = {"ok": 0, "warn": 0, "error": 0}
    for record in records:
        summary[record.status] += 1

    return {
        "summary": summary,
        "sources": [record.to_dict() for record in records],
        "crawler_engine": crawler_status,
        "xiaohongshu_api_base": env.get_xiaohongshu_api_base(config),
        "notes": [
            "诊断结果表示当前机器上的配置/公开端点可用性；平台风控会随时间变化。",
            "warn 不代表不可用，通常表示会走公开接口或搜索兜底，数据完整性可能较弱。",
        ],
    }


def render_json(report: Dict[str, Any]) -> Dict[str, Any]:
    """Return machine-readable diagnostic payload."""
    return report


def render_text(report: Dict[str, Any]) -> str:
    """Render diagnostics as concise Chinese text."""
    icon = {"ok": "✅", "warn": "⚠️", "error": "❌"}
    summary = report.get("summary", {})
    lines = [
        "last30days-cn 数据源诊断",
        f"可用 {summary.get('ok', 0)} / 警告 {summary.get('warn', 0)} / 错误 {summary.get('error', 0)}",
        "",
    ]
    for source in report.get("sources", []):
        status = source.get("status", "warn")
        lines.append(f"{icon.get(status, '•')} {source.get('label')} ({source.get('source')}): {source.get('reason')}")
        if source.get("fix"):
            lines.append(f"   建议: {source['fix']}")
        if status == "error" and source.get("fix_cli"):
            lines.append(f"   命令: {source['fix_cli']}")

    crawler = report.get("crawler_engine", {})
    lines.extend([
        "",
        f"Playwright: {'可用' if crawler.get('playwright_available') else '不可用'}",
        f"已缓存登录态: {', '.join(crawler.get('cached_logins') or []) or '无'}",
    ])
    if report.get("notes"):
        lines.append("")
        lines.extend(f"- {note}" for note in report["notes"])
    return "\n".join(lines)
