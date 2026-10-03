"""Output rendering for Chinese-platform research (last30days CN skill).

Author: Jesse (https://github.com/Jesseovo)

v4: rendering is driven by the source registry (``lib/sources.py``). This
fixes several v3 label bugs (小红书「收藏」显示的是分享数、知乎赞同数从不显示、
公众号名称/头条来源不显示) and adds overseas sources, per-source status with
the data path used, and a dark-mode-aware HTML report.
"""

import json
import os
import tempfile
from html import escape
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import schema, sources
from .version import DISPLAY_VERSION

OUTPUT_DIR = Path.home() / ".local" / "share" / "last30days" / "out"

# (attribute, label, kind) — kind "count" prints "1,234点赞", "star" prints "★1,234"
_ENGAGEMENT_FIELDS: Dict[str, Sequence[Tuple[str, str]]] = {
    "weibo": (("likes", "点赞"), ("reposts", "转发"), ("num_comments", "评论")),
    "xiaohongshu": (("likes", "点赞"), ("collects", "收藏"), ("num_comments", "评论"), ("shares", "分享")),
    "bilibili": (("views", "播放"), ("danmaku", "弹幕"), ("num_comments", "评论"), ("favorites", "收藏"), ("likes", "点赞")),
    "zhihu": (("voteups", "赞同"), ("num_comments", "评论"), ("collects", "收藏")),
    "douyin": (("views", "播放"), ("likes", "点赞"), ("num_comments", "评论"), ("shares", "分享")),
    "toutiao": (("reads", "阅读"), ("num_comments", "评论"), ("likes", "点赞"), ("hot_value", "热度")),
    "hackernews": (("score", "points"), ("num_comments", "评论")),
    "github": (("stars", "★"), ("num_comments", "评论")),
    "reddit": (("score", "upvotes"), ("num_comments", "评论")),
    "upstream": (("score", "分"), ("likes", "赞"), ("views", "播放"), ("num_comments", "评论"), ("reposts", "转发")),
}


def _safe_href(url: str) -> str:
    """仅放行 http/https 链接作为 HTML href，拦截 javascript:/data: 等可执行协议。

    抓取/搜索结果中的 URL 不可信，直接写入 href 会造成存储型 XSS（点击执行）。
    非 http(s) 链接一律降级为 ``#``。
    """
    cleaned = (url or "").strip()
    if cleaned.lower().startswith(("http://", "https://")):
        return cleaned
    return "#"


def _items(report: schema.Report, name: str):
    return getattr(report, name, None) or []


def _err(report: schema.Report, name: str):
    return getattr(report, name, None)


def _source_ids(report: schema.Report) -> List[str]:
    """Sources to render, in registry order."""
    active = set(report.active_sources()) if hasattr(report, "active_sources") else set()
    for sid in sources.SOURCES:
        if _items(report, sid) or _err(report, f"{sid}_error"):
            active.add(sid)
    return sources.ordered(active)


def _engine_badge(report: schema.Report) -> str:
    suffix = " · 缓存" if getattr(report, "from_cache", False) else ""
    return f"🌐 last30days-cn v{DISPLAY_VERSION} · 数据截至 {report.range_to}{suffix}"


def _xref_tag(item) -> str:
    """Return ' [同时见于: 微博, 知乎]' if item has cross_refs, else ''."""
    refs = getattr(item, "cross_refs", None)
    if not refs:
        return ""
    names = set()
    for ref_id in refs:
        label = sources.label_for_item_id(str(ref_id))
        if label:
            names.add(label)
    if names:
        return f" [同时见于: {', '.join(sorted(names))}]"
    return ""


def ensure_output_dir():
    """Ensure output directory exists. Supports env override and sandbox fallback."""
    global OUTPUT_DIR
    env_dir = os.environ.get("LAST30DAYS_OUTPUT_DIR")
    if env_dir:
        OUTPUT_DIR = Path(env_dir)

    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        OUTPUT_DIR = Path(tempfile.gettempdir()) / "last30days" / "out"
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _list_recent_count(items, range_from: str) -> int:
    return sum(1 for it in items if getattr(it, "date", None) and it.date >= range_from)


def _assess_data_freshness(report: schema.Report) -> dict:
    """Assess how much data is actually from the research window."""
    lists = [_items(report, sid) for sid in sources.SOURCES]
    recent = sum(_list_recent_count(lst, report.range_from) for lst in lists)
    total = sum(len(lst) for lst in lists)
    return {
        "total_recent": recent,
        "total_items": total,
        "is_sparse": recent < 5,
        "mostly_evergreen": total > 0 and recent < total * 0.3,
    }


def _fmt_number(value) -> str:
    if isinstance(value, float) and not value.is_integer():
        return f"{value:,.1f}"
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return str(value)


def format_engagement(source_id: str, eng) -> str:
    """Render known, non-zero engagement metrics for a source."""
    if not eng:
        return ""
    parts = []
    for attr, label in _ENGAGEMENT_FIELDS.get(source_id, ()):
        value = getattr(eng, attr, None)
        if value in (None, 0, 0.0, ""):
            continue
        if label == "★":
            parts.append(f"★{_fmt_number(value)}")
        else:
            parts.append(f"{_fmt_number(value)}{label}")
    return f" [{', '.join(parts)}]" if parts else ""


# Backward-compatible helpers (v3 names).
def _fmt_eng_weibo(eng) -> str:
    return format_engagement("weibo", eng)


def _fmt_eng_bilibili(eng) -> str:
    return format_engagement("bilibili", eng)


def _fmt_eng_douyin(eng) -> str:
    return format_engagement("douyin", eng)


def _fmt_eng_xhs(eng) -> str:
    return format_engagement("xiaohongshu", eng)


def _fmt_eng_zhihu(eng) -> str:
    return format_engagement("zhihu", eng)


def _fmt_eng_wechat(eng) -> str:
    return ""


def _one_line(text: str) -> str:
    return " ".join(str(text or "").split())


def _item_title(item) -> str:
    for attr in ("title", "text"):
        value = getattr(item, attr, None)
        if value:
            return _one_line(value)
    return ""


def _item_body(item) -> str:
    for attr in ("text", "desc", "excerpt", "snippet", "abstract", "description"):
        value = getattr(item, attr, None)
        if value:
            return _one_line(value)
    return ""


def _item_author(item) -> str:
    for attr in ("author_name", "author_handle", "channel_name", "author", "source_name", "source_domain"):
        value = getattr(item, attr, None)
        if value:
            return str(value)
    return ""


def _plain_text(item) -> str:
    for attr in ("title", "text", "snippet", "abstract", "excerpt", "desc", "description"):
        value = getattr(item, attr, None)
        if value:
            return str(value)
    return ""


def _who(source_id: str, item) -> str:
    if source_id in ("weibo", "douyin"):
        author = getattr(item, "author_handle", "") or getattr(item, "author_name", "")
        return f"@{author}" if author and not author.startswith(("微博热搜", "抖音热榜")) else (author or "")
    if source_id in ("hackernews", "github", "reddit", "upstream"):
        platform = sources.platform_label(getattr(item, "platform", source_id))
        container = getattr(item, "container", "")
        author = getattr(item, "author", "")
        bits = [platform]
        if container:
            bits.append(container)
        if author:
            bits.append(f"@{author}")
        return " · ".join(bits)
    return _item_author(item)


def _clusters_md_lines(report: schema.Report, limit: int = 8) -> list:
    """跨平台聚合热点（Markdown），无簇时返回空列表。"""
    clusters = getattr(report, "clusters", None) or []
    if not clusters:
        return []
    lines = ["### 🔗 跨平台聚合热点", ""]
    for c in clusters[:limit]:
        srcs = "、".join(c.get("sources", []))
        title = c.get("representative_title", "") or "(无标题)"
        lines.append(f"- **{title}** — 覆盖 {srcs}（{c.get('size', 0)} 条）")
        url = c.get("representative_url", "")
        if url:
            lines.append(f"  {url}")
    lines.append("")
    return lines


def _status_hint(report: schema.Report, source_id: str) -> str:
    status = (getattr(report, "source_status", None) or {}).get(source_id) or {}
    via = status.get("via") or {}
    if not via:
        return ""
    fallback_only = all(str(path).startswith(("site-search", "hot")) for path in via)
    if fallback_only:
        return "*注意：本平台结果全部来自热榜/公开搜索兜底，只有公开链接，缺少完整互动数据与精确日期。*"
    return ""


def _render_item_compact(source_id: str, item) -> List[str]:
    date = getattr(item, "date", None)
    date_str = f" ({date})" if date else " (日期未知)"
    conf = getattr(item, "date_confidence", "high")
    conf_str = f" [日期:{conf}]" if conf != "high" else ""
    eng_str = format_engagement(source_id, getattr(item, "engagement", None))
    who = _who(source_id, item)
    head = f"**{item.id}** (得分:{item.score}) {who}{date_str}{conf_str}{eng_str}{_xref_tag(item)}"
    lines = [head.replace("  ", " ")]

    title = _item_title(item)
    if source_id in ("weibo", "douyin"):
        snippet = title[:200] + ("..." if len(title) > 200 else "")
        lines.append(f"  {snippet}")
    else:
        lines.append(f"  {title[:160]}")
        body = _item_body(item)
        if body and body != title:
            lines.append(f"  {body[:150]}{'...' if len(body) > 150 else ''}")
    lines.append(f"  {item.url}")
    hashtags = getattr(item, "hashtags", None)
    if hashtags:
        lines.append(f"  话题: {' '.join('#' + h for h in hashtags[:8])}")
    if getattr(item, "why_relevant", ""):
        lines.append(f"  *{item.why_relevant}*")
    lines.append("")
    return lines


def render_compact(report: schema.Report, limit: int = 15, missing_keys: str = "none") -> str:
    """Render compact output for the assistant to synthesize."""
    lines = [_engine_badge(report), f"## 研究结果: {report.topic}", ""]
    if getattr(report, "from_cache", False):
        age = getattr(report, "cache_age_hours", None)
        age_text = f"约 {age:.1f} 小时前" if age is not None else "时间未知"
        lines.append(f"*缓存命中：{age_text}生成。使用 `--refresh` 可强制刷新。*")
        lines.append("")

    freshness = _assess_data_freshness(report)
    if freshness["is_sparse"]:
        lines.append("**⚠️ 近期数据较少** — 研究时间窗内可确认的讨论不多。")
        lines.append(f"仅 {freshness['total_recent']} 条可确认日期在 {report.range_from} 至 {report.range_to} 之间。")
        lines.append("下列结果可能含较早或常青内容，请向用户如实说明时效性。")
        lines.append("")

    lines.append(f"**日期范围:** {report.range_from} ~ {report.range_to}")
    lines.append(f"**模式:** {report.mode}")
    search_topic = getattr(report, "search_topic", "")
    if search_topic and search_topic != report.topic:
        lines.append(f"**平台检索词:** {search_topic}")
    lines.append("")

    if missing_keys != "none":
        lines.append("*💡 提示: 补齐各平台登录态/API Key 可多源交叉验证。*")
        lines.append("")

    lines.extend(_clusters_md_lines(report))

    for sid in _source_ids(report):
        spec = sources.get(sid)
        items = _items(report, sid)
        error = _err(report, f"{sid}_error")
        if not items and not error:
            continue
        lines.extend([f"### {spec.section}", ""])
        if not items:
            lines.extend([f"**错误:** {error}", ""])
            continue
        hint = _status_hint(report, sid)
        if hint:
            lines.extend([hint, ""])
        for item in items[:limit]:
            lines.extend(_render_item_compact(sid, item))

    return "\n".join(lines)


def render_quality_nudge(quality: dict) -> str:
    """Render the quality score nudge block."""
    nudge_text = quality.get("nudge_text")
    if not nudge_text:
        return ""
    return "\n".join(["---", f"**🔍 研究覆盖度: {quality['score_pct']}%**", "", nudge_text, ""])


def _via_text(status: Dict[str, Any]) -> str:
    via = status.get("via") or {}
    if not via:
        return ""
    parts = [f"{path}×{count}" if count > 1 else path for path, count in via.items()]
    return f"（路径: {', '.join(parts)}）"


def render_source_status(report: schema.Report, source_info: dict = None) -> str:
    """Render the source status footer."""
    source_info = source_info or {}
    lines = ["---", "**来源:**"]
    statuses = getattr(report, "source_status", None) or {}
    for sid in _source_ids(report):
        label = sources.label(sid)
        items = _items(report, sid)
        error = _err(report, f"{sid}_error")
        status = statuses.get(sid, {})
        elapsed = status.get("elapsed")
        timing = f" · {elapsed:.0f}s" if isinstance(elapsed, (int, float)) and elapsed >= 1 else ""
        if items:
            raw_count = status.get("raw_count")
            kept = f"（原始 {raw_count} 条，按时间窗/相关性保留）" if raw_count and raw_count != len(items) else ""
            lines.append(f"  ✅ {label}: {len(items)} 条{kept}{_via_text(status)}{timing}")
        elif status.get("state") == "timeout":
            lines.append(f"  ⏱️ {label}: 超时 — {error or ''}".rstrip(" —"))
        elif error:
            lines.append(f"  ❌ {label}: {error}")
        else:
            lines.append(f"  ⚠️ {label}: 0 条（检索成功但时间窗内无相关结果）")
    reason = source_info.get("baidu_skip_reason") or source_info.get("web_skip_reason")
    if reason:
        lines.append(f"  ⚡ 百度: {reason}")
    lines.append("")
    return "\n".join(lines)


def render_context_snippet(report: schema.Report) -> str:
    """Render reusable context snippet."""
    lines = [
        f"# 上下文: {report.topic}（{report.range_from} ~ {report.range_to}）",
        "",
        f"*生成时间: {report.generated_at[:10]} | 模式: {report.mode}*",
        "",
        "## 主要来源",
        "",
    ]
    all_items = []
    for sid in sources.SOURCES:
        for item in _items(report, sid)[:5]:
            text = _plain_text(item)
            all_items.append((item.score, sources.label(sid), (text[:50] + "...") if len(text) > 50 else text, item.url))
    all_items.sort(key=lambda x: -x[0])
    for _score, label, text, url in all_items[:8]:
        lines.append(f"- [{label}] {text} — {url}")
    clusters = getattr(report, "clusters", None) or []
    if clusters:
        lines.extend(["", "## 跨平台热点", ""])
        for c in clusters[:5]:
            lines.append(f"- {c.get('representative_title', '')}（{'、'.join(c.get('sources', []))}）")
    lines.extend(["", "## 摘要", "", "*完整报告见 report.md / report.html。*", ""])
    return "\n".join(lines)


def render_full_report(report: schema.Report) -> str:
    """Render the full markdown report."""
    lines = [
        _engine_badge(report),
        "",
        f"# {report.topic} — 近 {_window_days(report)} 天研究报告",
        "",
        f"**生成时间:** {report.generated_at}",
        f"**日期范围:** {report.range_from} ~ {report.range_to}",
        f"**模式:** {report.mode}",
        "",
    ]
    lines.extend(_clusters_md_lines(report))

    for sid in _source_ids(report):
        spec = sources.get(sid)
        items = _items(report, sid)
        error = _err(report, f"{sid}_error")
        if not items and not error:
            continue
        lines.extend([f"## {spec.section}", ""])
        if not items:
            lines.extend([f"> 错误：{error}", ""])
            continue
        for item in items:
            title = _item_title(item)
            lines.append(f"### {item.id}: {title[:80]}")
            lines.append("")
            who = _who(sid, item)
            if who:
                lines.append(f"- **作者/来源:** {who}")
            lines.append(f"- **链接:** {item.url}")
            lines.append(f"- **日期:** {item.date or '未知'} (置信: {getattr(item, 'date_confidence', 'low')})")
            lines.append(f"- **得分:** {item.score}/100")
            eng = format_engagement(sid, getattr(item, "engagement", None)).strip(" []")
            if eng:
                lines.append(f"- **互动:** {eng}")
            refs = _xref_tag(item).strip()
            if refs:
                lines.append(f"- **交叉验证:** {refs.strip('[]')}")
            if getattr(item, "why_relevant", ""):
                lines.append(f"- **相关性:** {item.why_relevant}")
            body = _item_body(item)
            if body and body != title:
                lines.extend(["", f"> {body[:400]}"])
            lines.append("")

    lines.append(render_source_status(report))
    return "\n".join(lines)


def _window_days(report: schema.Report) -> int:
    from datetime import datetime
    try:
        delta = datetime.strptime(report.range_to, "%Y-%m-%d") - datetime.strptime(report.range_from, "%Y-%m-%d")
        return max(1, delta.days)
    except (TypeError, ValueError):
        return 30


def write_outputs(report: schema.Report):
    """Write report.json, report.md, report.html, and last30days.context.md."""
    ensure_output_dir()
    with open(OUTPUT_DIR / "report.json", "w", encoding="utf-8") as f:
        json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)
    with open(OUTPUT_DIR / "report.md", "w", encoding="utf-8") as f:
        f.write(render_full_report(report))
    with open(OUTPUT_DIR / "report.html", "w", encoding="utf-8") as f:
        f.write(render_html_report(report))
    with open(OUTPUT_DIR / "last30days.context.md", "w", encoding="utf-8") as f:
        f.write(render_context_snippet(report))


def get_context_path() -> str:
    """Get path to context file."""
    return str(OUTPUT_DIR / "last30days.context.md")


def get_html_path() -> str:
    """Get path to the generated HTML report."""
    return str(OUTPUT_DIR / "report.html")


def _source_meta() -> Dict[str, Tuple[str, str]]:
    return {sid: (spec.label, spec.code) for sid, spec in sources.SOURCES.items()}


# Kept for compatibility with v3 callers/tests.
SOURCE_META = _source_meta()


def _engagement_total(item) -> int:
    eng = getattr(item, "engagement", None)
    if not eng:
        return 0
    total = 0
    for attr in ("views", "likes", "reposts", "shares", "collects", "favorites", "num_comments", "replies",
                 "reads", "danmaku", "voteups", "score", "stars"):
        value = getattr(eng, attr, None)
        if isinstance(value, (int, float)):
            total += int(value)
    hot = getattr(item, "hot_value", None)
    if isinstance(hot, (int, float)):
        total += int(hot)
    return total


def _collect_ranked_items(report: schema.Report, limit: int = 30):
    rows = []
    for source in SOURCE_META:
        for item in _items(report, source):
            rows.append((source, item))
    rows.sort(key=lambda pair: (getattr(pair[1], "score", 0), _engagement_total(pair[1])), reverse=True)
    return _diversify_ranked(rows, limit)


def _diversify_ranked(rows, limit: int, min_per_source: int = 2, relevance_floor: float = 0.25):
    """Keep top-ranked items while reserving a small floor for relevant minor sources."""
    if len(rows) <= limit:
        return rows

    selected = list(rows[:limit])
    selected_ids = {id(item) for _, item in selected}
    source_counts: Dict[str, int] = {}
    for source, _ in selected:
        source_counts[source] = source_counts.get(source, 0) + 1

    rank_index = {id(item): idx for idx, (_, item) in enumerate(rows)}

    for source in SOURCE_META:
        if source_counts.get(source, 0) >= min_per_source:
            continue
        eligible = [
            (src, item) for src, item in rows
            if src == source
            and id(item) not in selected_ids
            and getattr(item, "relevance", 0.0) >= relevance_floor
        ]
        for candidate in eligible:
            if source_counts.get(source, 0) >= min_per_source:
                break
            replace_idx = None
            for idx in range(len(selected) - 1, -1, -1):
                replace_source, _replace_item = selected[idx]
                if replace_source == source:
                    continue
                if source_counts.get(replace_source, 0) > min_per_source:
                    replace_idx = idx
                    break
            if replace_idx is None:
                break
            removed_source, removed_item = selected[replace_idx]
            selected_ids.remove(id(removed_item))
            source_counts[removed_source] -= 1
            selected[replace_idx] = candidate
            selected_ids.add(id(candidate[1]))
            source_counts[source] = source_counts.get(source, 0) + 1

    selected.sort(key=lambda pair: rank_index[id(pair[1])])
    return selected[:limit]


HTML_STYLE = """
:root {
  --paper:#fafaf8; --ink:#0a0a0a; --muted:#666; --line:#d8d8d4; --card:#ffffff;
  --accent:#002FA7; --accent-bright:#5B7BFF; --grey:#f0f0ee; --warn-bg:#fff4c2; --warn-line:#c18b00;
  --sans: Inter, "Helvetica Neue", Arial, "PingFang SC", "Microsoft YaHei", sans-serif;
  --mono: "JetBrains Mono", "SF Mono", Consolas, monospace;
}
@media (prefers-color-scheme: dark) {
  :root { --paper:#0f1115; --ink:#f2f2ee; --muted:#9a9a96; --line:#2a2d33; --card:#16191f;
          --accent:#7f9cff; --grey:#1b1e24; --warn-bg:#3a3110; --warn-line:#d6a400; }
}
* { box-sizing:border-box; }
body { margin:0; background:var(--paper); color:var(--ink); font-family:var(--sans); }
.page { min-height:100vh; }
.hero { min-height:64vh; padding:48px clamp(16px,5vw,72px); display:grid; grid-template-columns:7fr 5fr; gap:40px; align-items:end; background:linear-gradient(90deg, rgba(0,47,167,.10), transparent 42%), var(--paper); }
.kicker,.meta,.source-code,.source-state,.item-meta,.item-index,.item-score small,.footer { font-family:var(--mono); letter-spacing:.14em; text-transform:uppercase; }
.kicker { color:var(--accent); font-weight:700; margin-bottom:24px; }
h1 { font-size:clamp(40px,8vw,128px); line-height:.95; letter-spacing:-.02em; margin:0; font-weight:200; overflow-wrap:anywhere; }
.hero-copy { max-width:760px; font-size:clamp(17px,2vw,26px); line-height:1.4; color:var(--muted); margin-top:28px; }
.metrics { display:grid; grid-template-columns:repeat(2,1fr); gap:16px; }
.metric { border-top:2px solid var(--ink); padding-top:16px; min-height:120px; }
.metric strong { display:block; font-size:clamp(44px,7vw,104px); line-height:.85; letter-spacing:-.04em; }
.metric span { display:block; color:var(--muted); margin-top:12px; }
.band { padding:32px clamp(16px,5vw,72px); background:#002FA7; color:white; display:flex; justify-content:space-between; gap:24px; flex-wrap:wrap; }
.band strong { font-size:clamp(20px,3.4vw,48px); font-weight:300; letter-spacing:-.02em; }
.section { padding:48px clamp(16px,5vw,72px); }
.section-title { display:flex; justify-content:space-between; gap:24px; align-items:end; border-bottom:1px solid var(--line); padding-bottom:16px; margin-bottom:24px; flex-wrap:wrap; }
.section-title h2 { font-size:clamp(28px,4.6vw,68px); line-height:1; font-weight:250; margin:0; letter-spacing:-.02em; }
.sources { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:1px; background:var(--line); border:1px solid var(--line); }
.source-card { background:var(--card); padding:18px; min-height:150px; display:flex; flex-direction:column; }
.source-code,.source-state { color:var(--muted); font-size:12px; }
.source-state.err { color:#c0392b; }
.source-name { margin-top:14px; font-size:20px; }
.source-count { margin-top:auto; font-size:52px; line-height:.9; font-weight:800; letter-spacing:-.04em; }
.source-note { color:var(--muted); font-size:12px; margin-top:8px; line-height:1.45; overflow-wrap:anywhere; }
.notice { margin:0 clamp(16px,5vw,72px); padding:16px 20px; background:var(--warn-bg); border-left:4px solid var(--warn-line); }
.items { display:flex; flex-direction:column; border-top:1px solid var(--line); }
.item-card { display:grid; grid-template-columns:72px minmax(0,1fr) 112px; gap:24px; padding:22px 0; border-bottom:1px solid var(--line); }
.item-index { color:var(--accent); font-size:14px; padding-top:6px; }
.item-meta { display:flex; gap:14px; flex-wrap:wrap; color:var(--muted); font-size:12px; margin-bottom:10px; }
.item-main h3 { margin:0; font-size:clamp(18px,2.3vw,30px); line-height:1.25; font-weight:500; overflow-wrap:anywhere; }
.item-main p { color:var(--muted); line-height:1.55; margin:12px 0; }
.item-main a { color:var(--accent); overflow-wrap:anywhere; text-decoration:none; border-bottom:1px solid rgba(0,47,167,.35); }
.item-score { text-align:right; color:var(--accent); }
.item-score span { display:block; font-size:52px; line-height:.9; font-weight:800; letter-spacing:-.04em; }
.footer { padding:32px clamp(16px,5vw,72px); color:var(--muted); border-top:1px solid var(--line); font-size:12px; }
@media (max-width:900px) {
  .hero { grid-template-columns:1fr; min-height:auto; }
  .metrics,.sources { grid-template-columns:repeat(2,minmax(0,1fr)); }
  .item-card { grid-template-columns:40px minmax(0,1fr); gap:14px; }
  .item-score { grid-column:2; text-align:left; }
}
@media print {
  .hero { min-height:auto; }
  .item-card { break-inside:avoid; }
  a { color:var(--ink); }
}
"""


def render_html_report(report: schema.Report) -> str:
    """Render a Guizang-inspired Swiss/IKB HTML report."""
    ranked = _collect_ranked_items(report)
    meta = _source_meta()
    total = sum(len(_items(report, source)) for source in meta)
    shown_sources = [sid for sid in _source_ids(report)] or list(sources.CN_SOURCE_IDS)
    active_sources = [(source, len(_items(report, source))) for source in meta if _items(report, source)]
    top_score = getattr(ranked[0][1], "score", 0) if ranked else 0
    freshness = _assess_data_freshness(report)
    generated = escape(report.generated_at[:19].replace("T", " "))
    statuses = getattr(report, "source_status", None) or {}

    source_cards = []
    for source in shown_sources:
        cn, code = meta[source]
        count = len(_items(report, source))
        err = _err(report, f"{source}_error")
        status = statuses.get(source, {})
        state = "ERROR" if (err and not count) else ("ACTIVE" if count else "EMPTY")
        note = ""
        if err and not count:
            note = f'<div class="source-note">{escape(str(err)[:140])}</div>'
        elif status.get("via"):
            note = f'<div class="source-note">{escape(", ".join(status["via"].keys()))}</div>'
        source_cards.append(
            f'<div class="source-card"><div class="source-code">{escape(code)}</div>'
            f'<div class="source-name">{escape(cn)}</div><div class="source-count">{count}</div>'
            f'<div class="source-state{" err" if state == "ERROR" else ""}">{escape(state)}</div>{note}</div>'
        )

    item_cards = []
    for idx, (source, item) in enumerate(ranked, start=1):
        cn, code = meta[source]
        text = _plain_text(item)
        snippet = text[:220] + ("..." if len(text) > 220 else "")
        author = _who(source, item)
        date = getattr(item, "date", None) or "日期未知"
        score_value = getattr(item, "score", 0)
        reason = getattr(item, "why_relevant", "") or ""
        eng = format_engagement(source, getattr(item, "engagement", None)).strip(" []")
        url = getattr(item, "url", "") or "#"
        item_cards.append(
            '<article class="item-card">'
            f'<div class="item-index">{idx:02d}</div>'
            '<div class="item-main">'
            f'<div class="item-meta"><span>{escape(code)}</span><span>{escape(date)}</span>'
            f'<span>{escape(author)}</span>{f"<span>{escape(eng)}</span>" if eng else ""}</div>'
            f'<h3>{escape(snippet or url)}</h3>'
            f'<p>{escape(reason)}</p>'
            f'<a href="{escape(_safe_href(url), quote=True)}" target="_blank" rel="noopener noreferrer">{escape(url)}</a>'
            '</div>'
            f'<div class="item-score"><span>{score_value}</span><small>SCORE</small></div>'
            '</article>'
        )

    source_summary = ", ".join(f"{meta[s][0]} {n}" for s, n in active_sources) or "暂无可用来源"
    sparse_note = ""
    if freshness["is_sparse"]:
        sparse_note = '<div class="notice">近期可确认数据较少，请在最终分析中明确说明时效性和覆盖限制。</div>'

    cluster_section = ""
    clusters = getattr(report, "clusters", None) or []
    if clusters:
        cluster_rows = []
        for c in clusters[:8]:
            c_sources = "、".join(c.get("sources", []))
            c_title = c.get("representative_title", "") or "(无标题)"
            c_url = c.get("representative_url", "") or ""
            cluster_rows.append(
                '<article class="item-card">'
                f'<div class="item-index">×{c.get("size", 0)}</div>'
                '<div class="item-main">'
                f'<div class="item-meta"><span>{escape(c_sources)}</span></div>'
                f'<h3>{escape(c_title)}</h3>'
                f'<a href="{escape(_safe_href(c_url), quote=True)}" target="_blank" rel="noopener noreferrer">{escape(c_url)}</a>'
                '</div>'
                f'<div class="item-score"><span>{len(c.get("sources", []))}</span><small>PLATFORMS</small></div>'
                '</article>'
            )
        cluster_section = (
            '<section class="section">'
            '<div class="section-title"><h2>跨平台聚合热点</h2><div class="meta">cross-source clusters</div></div>'
            f'<div class="items">{"".join(cluster_rows)}</div>'
            '</section>'
        )

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>{escape(report.topic)} - last30days-cn</title>
<style>{HTML_STYLE}</style>
</head>
<body>
<main class="page">
  <section class="hero">
    <div>
      <div class="kicker">LAST30DAYS-CN / GUIZANG SWISS REPORT</div>
      <h1>{escape(report.topic)}</h1>
      <p class="hero-copy">覆盖 {escape(report.range_from)} 至 {escape(report.range_to)} 的平台讨论。视觉样式参考 guizang-ppt-skill 的 Swiss/IKB 报告语言，适合直接浏览、归档或打印。</p>
    </div>
    <div class="metrics">
      <div class="metric"><strong>{total}</strong><span>归一化结果</span></div>
      <div class="metric"><strong>{len(active_sources)}</strong><span>有结果的平台</span></div>
      <div class="metric"><strong>{top_score}</strong><span>最高综合分</span></div>
      <div class="metric"><strong>{freshness["total_recent"]}</strong><span>时间窗内可确认</span></div>
    </div>
  </section>
  <section class="band"><strong>{escape(source_summary)}</strong><div class="meta">generated {generated}</div></section>
  {sparse_note}
  {cluster_section}
  <section class="section">
    <div class="section-title"><h2>平台覆盖</h2><div class="meta">source matrix</div></div>
    <div class="sources">{''.join(source_cards)}</div>
  </section>
  <section class="section">
    <div class="section-title"><h2>高分结果</h2><div class="meta">ranked evidence</div></div>
    <div class="items">{''.join(item_cards) if item_cards else '<p>暂无结果。</p>'}</div>
  </section>
</main>
<footer class="footer">last30days-cn v{DISPLAY_VERSION} · HTML renderer inspired by op7418/guizang-ppt-skill · Generated locally.</footer>
</body>
</html>"""
