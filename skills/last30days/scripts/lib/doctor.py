"""Human-readable source diagnostics for last30days-cn.

v4: diagnostics are honest about *which path* each platform will use:
- ``ok``    — a primary path (API / login session / verified public endpoint) works
- ``warn``  — only degraded paths remain (hot lists / public web-search fallback),
              or a fix is recommended
- ``error`` — nothing usable
Login state for browser sessions, live probes for the public endpoints,
browser health (optional real launch) and the web-search fallback engines are
reported too. v3 reported 小红书 as ``true`` even when every path was dead
(issue #8 comment).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List

from . import crawler_bridge, env, upstream_bridge, websearch
from .version import DISPLAY_VERSION

INSTALL_PLAYWRIGHT = "python -m pip install playwright && python -m playwright install chromium"


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


def _record(source, label, status, available, reason, fix="", fix_cli="") -> SourceRecord:
    return SourceRecord(source, label, status, available, reason, fix, fix_cli)


def _login_cli(platform: str) -> str:
    return f"python scripts/last30days.py login {platform}"


def build_report(config: Dict[str, Any], probe_browser: bool = False) -> Dict[str, Any]:
    """Build a source-by-source diagnostic report."""
    crawler_status = crawler_bridge.get_crawler_status()
    has_playwright = bool(crawler_status.get("playwright_available"))
    logins = {p: crawler_bridge.has_login(p) for p in crawler_bridge.LOGIN_SPECS}
    browser_probe = None
    if probe_browser and has_playwright:
        ok, message = crawler_bridge.probe_browser_launch()
        browser_probe = {"ok": ok, "message": message}
        if not ok:
            has_playwright = False

    records: List[SourceRecord] = []

    # 微博 -------------------------------------------------------------
    weibo_cred = bool(config.get("WEIBO_ACCESS_TOKEN") or config.get("WEIBO_COOKIE"))
    weibo_browser = has_playwright and logins.get("weibo")
    hot_ok = env.probe_weibo_hot()
    if weibo_cred or weibo_browser:
        records.append(_record("weibo", "微博", "ok", True,
                               "已配置 WEIBO_COOKIE/Token 或浏览器已登录微博，可全文搜索"))
    else:
        records.append(_record(
            "weibo", "微博", "warn", hot_ok,
            "微博搜索现需登录；当前只能用热搜榜匹配 + 公开搜索兜底" + ("" if hot_ok else "（热搜接口也不可达）"),
            "运行 login weibo（需 Playwright）或在 .env 配置 WEIBO_COOKIE",
            _login_cli("weibo"),
        ))

    # 小红书 -----------------------------------------------------------
    paths = env.xiaohongshu_paths(config)
    if paths["mcp"]:
        records.append(_record("xiaohongshu", "小红书", "ok", True, "xiaohongshu-mcp 已登录可用"))
    elif paths["browser"] and paths["browser_logged_in"]:
        records.append(_record("xiaohongshu", "小红书", "ok", True, "浏览器已保存小红书登录态"))
    else:
        reason = "未登录小红书：只能走公开搜索兜底（仅链接，无互动数据）"
        if not paths["browser"]:
            reason += "；Playwright 不可用"
        records.append(_record(
            "xiaohongshu", "小红书", "warn", True, reason,
            "运行 login xiaohongshu 扫码登录，或部署 xiaohongshu-mcp 并配置 XIAOHONGSHU_API_BASE",
            _login_cli("xiaohongshu") if paths["browser"] else INSTALL_PLAYWRIGHT,
        ))

    # B站 --------------------------------------------------------------
    bilibili_ok = env.probe_bilibili()
    records.append(_record(
        "bilibili", "B站",
        "ok" if bilibili_ok else ("warn" if has_playwright else "error"),
        bilibili_ok or has_playwright,
        "WBI 签名搜索可用" if bilibili_ok else "B站搜索接口探测失败（可能被 412 风控）" + ("；可尝试浏览器兜底" if has_playwright else ""),
        "" if bilibili_ok else "稍后重试，或在 .env 配置 BILIBILI_COOKIE（浏览器复制的 SESSDATA 等）",
        "" if bilibili_ok else INSTALL_PLAYWRIGHT,
    ))

    # 知乎 -------------------------------------------------------------
    if config.get("ZHIHU_COOKIE"):
        zhihu_ok = env.probe_zhihu()
        records.append(_record(
            "zhihu", "知乎", "ok" if zhihu_ok else "warn", True,
            "ZHIHU_COOKIE 搜索可用" if zhihu_ok else "ZHIHU_COOKIE 可能已过期或触发验证；会尝试浏览器/公开搜索",
            "" if zhihu_ok else "重新从浏览器复制 Cookie，或运行 login zhihu",
            "" if zhihu_ok else _login_cli("zhihu"),
        ))
    elif has_playwright and logins.get("zhihu"):
        records.append(_record("zhihu", "知乎", "ok", True, "浏览器已保存知乎登录态"))
    else:
        records.append(_record(
            "zhihu", "知乎", "warn", True,
            "知乎搜索需要登录；当前只能用热榜匹配 + 公开搜索兜底",
            "配置 ZHIHU_COOKIE 或运行 login zhihu",
            _login_cli("zhihu") if has_playwright else INSTALL_PLAYWRIGHT,
        ))

    # 抖音 -------------------------------------------------------------
    if config.get("TIKHUB_API_KEY") or config.get("DOUYIN_API_KEY"):
        records.append(_record("douyin", "抖音", "ok", True, "已配置 TikHub API"))
    elif has_playwright and logins.get("douyin"):
        records.append(_record("douyin", "抖音", "ok", True, "浏览器已保存抖音登录态（页面自行签名）"))
    else:
        records.append(_record(
            "douyin", "抖音", "warn", True,
            "抖音搜索需要签名/登录；当前只能用热榜匹配 + 公开搜索兜底",
            "配置 TIKHUB_API_KEY，或运行 login douyin",
            _login_cli("douyin") if has_playwright else INSTALL_PLAYWRIGHT,
        ))

    # 微信 -------------------------------------------------------------
    if config.get("WECHAT_API_KEY"):
        records.append(_record("wechat", "微信公众号", "ok", True, "已配置 WECHAT_API_KEY"))
    else:
        sogou_ok = env.probe_wechat()
        records.append(_record(
            "wechat", "微信公众号", "ok" if sogou_ok else "warn", True,
            "搜狗微信公开搜索可用" if sogou_ok else "搜狗微信探测失败（可能触发反爬）；会尝试公开搜索兜底",
            "" if sogou_ok else "稍后重试或配置 WECHAT_API_KEY",
        ))

    # 百度 -------------------------------------------------------------
    if env.is_baidu_api_available(config):
        records.append(_record("baidu", "百度", "ok", True, "已配置千帆 AI 搜索 BAIDU_API_KEY"))
    else:
        records.append(_record(
            "baidu", "百度", "warn", True,
            "未配置 BAIDU_API_KEY；使用百度网页搜索（常被安全验证拦截）+ 多引擎兜底",
            "在百度智能云千帆开通「AI 搜索」并配置 BAIDU_API_KEY",
        ))

    # 头条 -------------------------------------------------------------
    toutiao_ok = env.probe_toutiao()
    records.append(_record(
        "toutiao", "今日头条", "ok" if toutiao_ok else "warn", True,
        "头条资讯搜索（so.toutiao.com）可用" if toutiao_ok else "头条资讯搜索探测失败；会使用热榜与公开搜索兜底",
    ))

    summary = {"ok": 0, "warn": 0, "error": 0}
    for record in records:
        summary[record.status] += 1

    upstream = upstream_bridge.status()
    return {
        "version": DISPLAY_VERSION,
        "summary": summary,
        "sources": [record.to_dict() for record in records],
        "crawler_engine": crawler_status,
        "browser_probe": browser_probe,
        "logins": {p: crawler_bridge.login_status(p) for p in crawler_bridge.LOGIN_SPECS},
        "xiaohongshu_api_base": env.discover_xiaohongshu_mcp(config),
        "websearch": {
            "engines": websearch.configured_engines(),
            "blocked_this_run": websearch.blocked_engines(),
        },
        "overseas": {
            "native": ["hackernews", "github", "reddit"],
            "github_token": bool(config.get("GITHUB_TOKEN")),
            "upstream_bridge": upstream,
        },
        "config_source": config.get("_CONFIG_SOURCE"),
        "notes": [
            "ok = 主路径可用；warn = 只剩热榜/公开搜索等降级路径或建议修复；error = 无可用路径。",
            "平台风控随时间与网络环境变化；--diagnose --probe-browser 会真实启动一次浏览器。",
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
        f"last30days-cn {report.get('version', '')} 数据源诊断",
        f"可用 {summary.get('ok', 0)} / 降级 {summary.get('warn', 0)} / 不可用 {summary.get('error', 0)}",
        "",
    ]
    for source in report.get("sources", []):
        status = source.get("status", "warn")
        lines.append(f"{icon.get(status, '•')} {source.get('label')} ({source.get('source')}): {source.get('reason')}")
        if source.get("fix"):
            lines.append(f"   建议: {source['fix']}")
        if source.get("fix_cli"):
            lines.append(f"   命令: {source['fix_cli']}")

    crawler = report.get("crawler_engine", {}) or {}
    browser = crawler.get("browser") or {}
    available = "可用" if crawler.get("playwright_available") else "不可用"
    if browser.get("mode") == "disabled":
        available += "（已通过 LAST30DAYS_DISABLE_BROWSER 禁用）"
    external = browser.get("path") or browser.get("channel") or "未指定"
    if browser.get("path") and not browser.get("path_exists"):
        external += "（路径不存在！）"
    lines.extend([
        "",
        "浏览器（Playwright）",
        f"  状态: {available}",
        f"  模式: {browser.get('mode', 'managed')}  外部浏览器: {external}",
    ])
    if browser.get("launch_failure"):
        lines.append(f"  本次运行启动失败: {browser['launch_failure'][:200]}")
    probe = report.get("browser_probe")
    if probe:
        lines.append(f"  启动测试: {'✅ ' if probe.get('ok') else '❌ '}{probe.get('message')}")
    else:
        lines.append("  启动测试: 未执行（加 --probe-browser 真实启动一次）")

    lines.append("")
    lines.append("登录态（login <平台> 保存）")
    for platform, info in (report.get("logins") or {}).items():
        state = "已登录" if info.get("logged_in") else "未登录"
        extra = f"，有效期至 {info['expires']}" if info.get("expires") else ""
        lines.append(f"  {info.get('label', platform)}: {state}{extra}")

    web = report.get("websearch") or {}
    lines.extend(["", f"公开搜索兜底引擎: {' → '.join(web.get('engines') or [])}"])

    overseas = report.get("overseas") or {}
    upstream = overseas.get("upstream_bridge") or {}
    lines.extend([
        "",
        "海外源（opt-in，--search global / --global）",
        f"  Hacker News / GitHub / Reddit: 免 Key 可用{'（已配置 GITHUB_TOKEN）' if overseas.get('github_token') else ''}",
        f"  上游 last30days 桥接: "
        + (f"已就绪（{upstream.get('script')}）" if upstream.get("ready")
           else (f"已安装但 {upstream.get('python_note')}" if upstream.get("installed")
                 else "未安装（npx skills add mvanhorn/last30days-skill -g）")),
    ])
    if report.get("config_source"):
        lines.append(f"\n配置来源: {report['config_source']}")
    if report.get("notes"):
        lines.append("")
        lines.extend(f"- {note}" for note in report["notes"])
    return "\n".join(lines)
