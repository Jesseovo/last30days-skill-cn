"""Output rendering for Chinese-platform research (last30days CN skill).

Author: Jesse (https://github.com/Jesseovo)
"""

import json
import os
import tempfile
from html import escape
from pathlib import Path

from . import schema
from .version import DISPLAY_VERSION

OUTPUT_DIR = Path.home() / ".local" / "share" / "last30days" / "out"


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


def _engine_badge(report: schema.Report) -> str:
    suffix = " · 缓存" if getattr(report, "from_cache", False) else ""
    return f"🌐 last30days-cn v{DISPLAY_VERSION} · 数据截至 {report.range_to}{suffix}"


def _xref_tag(item) -> str:
    """Return ' [同时见于: 微博, 知乎]' if item has cross_refs, else ''."""
    refs = getattr(item, "cross_refs", None)
    if not refs:
        return ""
    source_names = set()
    for ref_id in refs:
        rid = str(ref_id)
        if rid.startswith("WB"):
            source_names.add("微博")
        elif rid.startswith("XHS"):
            source_names.add("小红书")
        elif rid.startswith("BL"):
            source_names.add("B站")
        elif rid.startswith("ZH"):
            source_names.add("知乎")
        elif rid.startswith("DY"):
            source_names.add("抖音")
        elif rid.startswith("WX"):
            source_names.add("微信")
        elif rid.startswith("BD"):
            source_names.add("百度")
        elif rid.startswith("TT"):
            source_names.add("头条")
    if source_names:
        return f" [同时见于: {', '.join(sorted(source_names))}]"
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
    """Assess how much data is actually from the last 30 days."""
    lists = [
        _items(report, "weibo"),
        _items(report, "xiaohongshu"),
        _items(report, "bilibili"),
        _items(report, "zhihu"),
        _items(report, "douyin"),
        _items(report, "wechat"),
        _items(report, "baidu"),
        _items(report, "toutiao"),
    ]
    recent = sum(_list_recent_count(lst, report.range_from) for lst in lists)
    total = sum(len(lst) for lst in lists)
    return {
        "total_recent": recent,
        "total_items": total,
        "is_sparse": recent < 5,
        "mostly_evergreen": total > 0 and recent < total * 0.3,
    }


def _fmt_eng_weibo(eng) -> str:
    if not eng:
        return ""
    parts = []
    if eng.likes is not None:
        parts.append(f"{eng.likes}点赞")
    if eng.reposts is not None:
        parts.append(f"{eng.reposts}转发")
    c = eng.num_comments if eng.num_comments is not None else getattr(eng, "replies", None)
    if c is not None:
        parts.append(f"{c}评论")
    return f" [{', '.join(parts)}]" if parts else ""


def _fmt_eng_bilibili(eng) -> str:
    if not eng:
        return ""
    parts = []
    if eng.views is not None:
        parts.append(f"{eng.views:,}播放")
    dm = getattr(eng, "danmaku", None) or getattr(eng, "danmu", None)
    if dm is not None:
        parts.append(f"{dm}弹幕")
    coins = getattr(eng, "coins", None)
    if coins is not None:
        parts.append(f"{coins}投币")
    fav = getattr(eng, "favorites", None) or getattr(eng, "fav", None)
    if fav is not None:
        parts.append(f"{fav}收藏")
    if eng.likes is not None:
        parts.append(f"{eng.likes}点赞")
    return f" [{', '.join(parts)}]" if parts else ""


def _fmt_eng_douyin(eng) -> str:
    if not eng:
        return ""
    parts = []
    if eng.views is not None:
        parts.append(f"{eng.views:,}播放")
    if eng.likes is not None:
        parts.append(f"{eng.likes}点赞")
    c = eng.num_comments if eng.num_comments is not None else getattr(eng, "replies", None)
    if c is not None:
        parts.append(f"{c}评论")
    if eng.shares is not None:
        parts.append(f"{eng.shares}转发")
    return f" [{', '.join(parts)}]" if parts else ""


def _fmt_eng_xhs(eng) -> str:
    if not eng:
        return ""
    parts = []
    if eng.likes is not None:
        parts.append(f"{eng.likes}点赞")
    c = eng.num_comments if eng.num_comments is not None else getattr(eng, "replies", None)
    if c is not None:
        parts.append(f"{c}评论")
    if eng.shares is not None:
        parts.append(f"{eng.shares}收藏")
    return f" [{', '.join(parts)}]" if parts else ""


def _fmt_eng_zhihu(eng) -> str:
    if not eng:
        return ""
    parts = []
    if eng.score is not None:
        parts.append(f"{eng.score}赞同")
    if eng.num_comments is not None:
        parts.append(f"{eng.num_comments}评论")
    return f" [{', '.join(parts)}]" if parts else ""


def _fmt_eng_wechat(eng) -> str:
    if not eng:
        return ""
    parts = []
    reads = getattr(eng, "reads", None) or getattr(eng, "views", None)
    if reads is not None:
        parts.append(f"{reads}阅读")
    if eng.likes is not None:
        parts.append(f"{eng.likes}点赞")
    return f" [{', '.join(parts)}]" if parts else ""


def _clusters_md_lines(report: schema.Report, limit: int = 8) -> list:
    """跨平台聚合热点（Markdown），无簇时返回空列表。"""
    clusters = getattr(report, "clusters", None) or []
    if not clusters:
        return []
    lines = ["### 🔗 跨平台聚合热点", ""]
    for c in clusters[:limit]:
        sources = "、".join(c.get("sources", []))
        title = c.get("representative_title", "") or "(无标题)"
        lines.append(f"- **{title}** — 覆盖 {sources}（{c.get('size', 0)} 条）")
        url = c.get("representative_url", "")
        if url:
            lines.append(f"  {url}")
    lines.append("")
    return lines


def render_compact(report: schema.Report, limit: int = 15, missing_keys: str = "none") -> str:
    """Render compact output for the assistant to synthesize."""
    lines = []

    lines.append(_engine_badge(report))
    lines.append(f"## 研究结果: {report.topic}")
    lines.append("")
    if getattr(report, "from_cache", False):
        age = getattr(report, "cache_age_hours", None)
        age_text = f"约 {age:.1f} 小时前" if age is not None else "时间未知"
        lines.append(f"*缓存命中：{age_text}生成。使用 `--refresh` 可强制刷新。*")
        lines.append("")

    freshness = _assess_data_freshness(report)
    if freshness["is_sparse"]:
        lines.append("**⚠️ 近期数据较少** — 近 30 天内可确认的讨论不多。")
        lines.append(f"仅 {freshness['total_recent']} 条可确认日期在 {report.range_from} 至 {report.range_to} 之间。")
        lines.append("下列结果可能含较早或常青内容，请向用户如实说明时效性。")
        lines.append("")

    lines.append(f"**日期范围:** {report.range_from} ~ {report.range_to}")
    lines.append(f"**模式:** {report.mode}")
    rw = getattr(report, "resolved_weibo_handle", None)
    if rw:
        lines.append(f"**解析的微博用户:** @{rw}")
    lines.append("")

    if missing_keys != "none":
        lines.append("*💡 提示: 补齐各平台 API Key 可多源交叉验证。*")
        lines.append("")

    lines.extend(_clusters_md_lines(report))

    weibo_e = _err(report, "weibo_error")
    weibo = _items(report, "weibo")
    if weibo_e:
        lines.extend(["### 微博动态", "", f"**错误:** {weibo_e}", ""])
    elif weibo:
        lines.extend(["### 微博动态", ""])
        for item in weibo[:limit]:
            date_str = f" ({item.date})" if item.date else " (日期未知)"
            conf_str = f" [日期:{item.date_confidence}]" if getattr(item, "date_confidence", "high") != "high" else ""
            eng_str = _fmt_eng_weibo(item.engagement)
            lines.append(
                f"**{item.id}** (得分:{item.score}) @{item.author_handle}{date_str}{conf_str}{eng_str}{_xref_tag(item)}"
            )
            text = getattr(item, "text", "") or ""
            snippet = text[:200] + ("..." if len(text) > 200 else "")
            lines.append(f"  {snippet}")
            lines.append(f"  {item.url}")
            lines.append(f"  *{item.why_relevant}*")
            if getattr(item, "top_comments", None) and item.top_comments and item.top_comments[0].score >= 10:
                tc = item.top_comments[0]
                excerpt = tc.excerpt[:200]
                if len(tc.excerpt) > 200:
                    excerpt = excerpt.rstrip() + "..."
                lines.append(f'  💬 热评 ({tc.score}点赞): "{excerpt}"')
            if getattr(item, "comment_insights", None):
                lines.append("  观点摘要:")
                for insight in item.comment_insights[:3]:
                    lines.append(f"    - {insight}")
            lines.append("")

    xhs_e = _err(report, "xiaohongshu_error")
    xhs = _items(report, "xiaohongshu")
    if xhs_e:
        lines.extend(["### 小红书笔记", "", f"**错误:** {xhs_e}", ""])
    elif xhs:
        lines.extend(["### 小红书笔记", ""])
        for item in xhs[:limit]:
            date_str = f" ({item.date})" if item.date else ""
            conf_str = f" [日期:{item.date_confidence}]" if getattr(item, "date_confidence", "high") != "high" else ""
            eng_str = _fmt_eng_xhs(item.engagement)
            author = getattr(item, "author_name", "") or getattr(item, "author_handle", "")
            title = getattr(item, "title", None) or (getattr(item, "text", "") or "")[:80]
            lines.append(f"**{item.id}** (得分:{item.score}) {author}{date_str}{conf_str}{eng_str}{_xref_tag(item)}")
            lines.append(f"  {title}")
            lines.append(f"  {item.url}")
            if getattr(item, "hashtags", None):
                tags = " ".join(f"#{t}" for t in item.hashtags[:8])
                lines.append(f"  话题: {tags}")
            lines.append(f"  *{item.why_relevant}*")
            lines.append("")

    bl_e = _err(report, "bilibili_error")
    bl = _items(report, "bilibili")
    if bl_e:
        lines.extend(["### B站视频", "", f"**错误:** {bl_e}", ""])
    elif bl:
        lines.extend(["### B站视频", ""])
        for item in bl[:limit]:
            date_str = f" ({item.date})" if item.date else ""
            eng_str = _fmt_eng_bilibili(item.engagement)
            lines.append(
                f"**{item.id}** (得分:{item.score}) {item.channel_name}{date_str}{eng_str}{_xref_tag(item)}"
            )
            lines.append(f"  {item.title}")
            lines.append(f"  {item.url}")
            if getattr(item, "transcript_highlights", None):
                lines.append("  要点:")
                for hl in item.transcript_highlights[:5]:
                    lines.append(f'    - "{hl}"')
            if getattr(item, "transcript_snippet", None) and item.transcript_snippet:
                wc = len(item.transcript_snippet.split())
                lines.append(f"  <details><summary>字幕/文稿节选 ({wc} 词)</summary>")
                lines.append(f"  {item.transcript_snippet}")
                lines.append("  </details>")
            lines.append(f"  *{item.why_relevant}*")
            lines.append("")

    zh_e = _err(report, "zhihu_error")
    zh = _items(report, "zhihu")
    if zh_e:
        lines.extend(["### 知乎问答", "", f"**错误:** {zh_e}", ""])
    elif zh:
        lines.extend(["### 知乎问答", ""])
        for item in zh[:limit]:
            date_str = f" ({item.date})" if item.date else ""
            eng_str = _fmt_eng_zhihu(item.engagement)
            zurl = getattr(item, "zhihu_url", None) or item.url
            lines.append(
                f"**{item.id}** (得分:{item.score}) {getattr(item, 'author', '')}{date_str}{eng_str}{_xref_tag(item)}"
            )
            lines.append(f"  {item.title}")
            lines.append(f"  {zurl}")
            lines.append(f"  *{item.why_relevant}*")
            if getattr(item, "comment_insights", None):
                lines.append("  观点摘要:")
                for insight in item.comment_insights[:3]:
                    lines.append(f"    - {insight}")
            lines.append("")

    dy_e = _err(report, "douyin_error")
    dy = _items(report, "douyin")
    if dy_e:
        lines.extend(["### 抖音视频", "", f"**错误:** {dy_e}", ""])
    elif dy:
        lines.extend(["### 抖音视频", ""])
        for item in dy[:limit]:
            date_str = f" ({item.date})" if item.date else ""
            eng_str = _fmt_eng_douyin(item.engagement)
            auth = getattr(item, "author_name", "")
            txt = getattr(item, "text", "") or ""
            snippet = txt[:200] + ("..." if len(txt) > 200 else "")
            lines.append(f"**{item.id}** (得分:{item.score}) @{auth}{date_str}{eng_str}{_xref_tag(item)}")
            lines.append(f"  {snippet}")
            lines.append(f"  {item.url}")
            cap = getattr(item, "caption_snippet", None)
            if cap and cap != txt[: len(cap)]:
                cs = cap[:200]
                if len(cap) > 200:
                    cs += "..."
                lines.append(f"  文案: {cs}")
            if getattr(item, "hashtags", None):
                lines.append(f"  话题: {' '.join('#' + h for h in item.hashtags[:8])}")
            lines.append(f"  *{item.why_relevant}*")
            lines.append("")

    wx_e = _err(report, "wechat_error")
    wx = _items(report, "wechat")
    if wx_e:
        lines.extend(["### 微信公众号文章", "", f"**错误:** {wx_e}", ""])
    elif wx:
        lines.extend(["### 微信公众号文章", ""])
        for item in wx[:limit]:
            date_str = f" ({item.date})" if item.date else ""
            eng_str = _fmt_eng_wechat(getattr(item, "engagement", None))
            acct = getattr(item, "account_name", None) or getattr(item, "author_name", "") or getattr(item, "author", "")
            lines.append(f"**{item.id}** (得分:{item.score}) {acct}{date_str}{eng_str}{_xref_tag(item)}")
            lines.append(f"  {item.title}")
            lines.append(f"  {item.url}")
            sn = getattr(item, "snippet", "") or ""
            if sn:
                lines.append(f"  {sn[:150]}...")
            lines.append(f"  *{item.why_relevant}*")
            lines.append("")

    bd_e = _err(report, "baidu_error")
    bd = _items(report, "baidu")
    if bd_e:
        lines.extend(["### 百度搜索结果", "", f"**错误:** {bd_e}", ""])
    elif bd:
        lines.extend(["### 百度搜索结果", ""])
        for item in bd[:limit]:
            date_str = f" ({item.date})" if item.date else " (日期未知)"
            conf_str = f" [日期:{item.date_confidence}]" if getattr(item, "date_confidence", "high") != "high" else ""
            lines.append(
                f"**{item.id}** [百度] (得分:{item.score}) {item.source_domain}{date_str}{conf_str}{_xref_tag(item)}"
            )
            lines.append(f"  {item.title}")
            lines.append(f"  {item.url}")
            snip = (getattr(item, "snippet", None) or "")[:150]
            lines.append(f"  {snip}...")
            lines.append(f"  *{item.why_relevant}*")
            lines.append("")

    tt_e = _err(report, "toutiao_error")
    tt = _items(report, "toutiao")
    if tt_e:
        lines.extend(["### 今日头条资讯", "", f"**错误:** {tt_e}", ""])
    elif tt:
        lines.extend(["### 今日头条资讯", ""])
        for item in tt[:limit]:
            date_str = f" ({item.date})" if item.date else ""
            conf_str = f" [日期:{item.date_confidence}]" if getattr(item, "date_confidence", "high") != "high" else ""
            dom = getattr(item, "source_domain", "") or getattr(item, "source", "")
            lines.append(f"**{item.id}** [头条] (得分:{item.score}) {dom}{date_str}{conf_str}{_xref_tag(item)}")
            title = getattr(item, "title", "")
            lines.append(f"  {title}")
            lines.append(f"  {item.url}")
            sn = (getattr(item, "snippet", None) or getattr(item, "summary", None) or "")[:150]
            if sn:
                lines.append(f"  {sn}...")
            lines.append(f"  *{getattr(item, 'why_relevant', '')}*")
            lines.append("")

    return "\n".join(lines)


def render_quality_nudge(quality: dict) -> str:
    """Render the quality score nudge block."""
    nudge_text = quality.get("nudge_text")
    if not nudge_text:
        return ""

    lines = [
        "---",
        f"**🔍 研究覆盖度: {quality['score_pct']}%**",
        "",
        nudge_text,
        "",
    ]
    return "\n".join(lines)


def render_source_status(report: schema.Report, source_info: dict = None) -> str:
    """Render source status footer (Chinese platforms)."""
    if source_info is None:
        source_info = {}

    lines = ["---", "**来源:**"]

    def line_ok(name: str, n: int, extra: str = ""):
        lines.append(f"  ✅ {name}: {n} 条{extra}")

    def line_err(name: str, err: str):
        lines.append(f"  ❌ {name}: 错误 — {err}")

    weibo = _items(report, "weibo")
    weibo_e = _err(report, "weibo_error")
    if weibo_e:
        line_err("微博", weibo_e)
    elif weibo:
        line_ok("微博", len(weibo))

    xhs = _items(report, "xiaohongshu")
    xhs_e = _err(report, "xiaohongshu_error")
    if xhs_e:
        line_err("小红书", xhs_e)
    elif xhs:
        line_ok("小红书", len(xhs))

    bl = _items(report, "bilibili")
    bl_e = _err(report, "bilibili_error")
    if bl_e:
        line_err("B站", bl_e)
    elif bl:
        n_tr = sum(1 for v in bl if getattr(v, "transcript_snippet", None))
        line_ok("B站", len(bl), f"（{n_tr} 条含字幕/文稿）")

    zh = _items(report, "zhihu")
    zh_e = _err(report, "zhihu_error")
    if zh_e:
        line_err("知乎", zh_e)
    elif zh:
        line_ok("知乎", len(zh))

    dy = _items(report, "douyin")
    dy_e = _err(report, "douyin_error")
    if dy_e:
        line_err("抖音", dy_e)
    elif dy:
        line_ok("抖音", len(dy))

    wx = _items(report, "wechat")
    wx_e = _err(report, "wechat_error")
    if wx_e:
        line_err("微信", wx_e)
    elif wx:
        line_ok("微信公众号", len(wx))

    bd = _items(report, "baidu")
    bd_e = _err(report, "baidu_error")
    if bd_e:
        line_err("百度", bd_e)
    elif bd:
        line_ok("百度", len(bd))
    else:
        reason = source_info.get("baidu_skip_reason") or source_info.get("web_skip_reason")
        if reason:
            lines.append(f"  ⚡ 百度: {reason}")

    tt = _items(report, "toutiao")
    tt_e = _err(report, "toutiao_error")
    if tt_e:
        line_err("头条", tt_e)
    elif tt:
        line_ok("今日头条", len(tt))

    lines.append("")
    return "\n".join(lines)


def render_context_snippet(report: schema.Report) -> str:
    """Render reusable context snippet (Chinese sources)."""
    lines = [
        f"# 上下文: {report.topic}（近 30 天）",
        "",
        f"*生成时间: {report.generated_at[:10]} | 模式: {report.mode}*",
        "",
        "## 主要来源",
        "",
    ]

    all_items = []
    for item in _items(report, "weibo")[:5]:
        t = (getattr(item, "text", "") or "")[:50] + "..."
        all_items.append((item.score, "微博", t, item.url))
    for item in _items(report, "xiaohongshu")[:5]:
        t = (getattr(item, "title", None) or getattr(item, "text", "") or "")[:50] + "..."
        all_items.append((item.score, "小红书", t, item.url))
    for item in _items(report, "bilibili")[:5]:
        tit = item.title
        all_items.append((item.score, "B站", (tit[:50] + "...") if len(tit) > 50 else tit, item.url))
    for item in _items(report, "zhihu")[:5]:
        tit = item.title
        all_items.append((item.score, "知乎", (tit[:50] + "...") if len(tit) > 50 else tit, item.url))
    for item in _items(report, "douyin")[:5]:
        t = (getattr(item, "text", "") or "")[:50] + "..."
        all_items.append((item.score, "抖音", t, item.url))
    for item in _items(report, "wechat")[:5]:
        tit = item.title
        all_items.append((item.score, "微信", (tit[:50] + "...") if len(tit) > 50 else tit, item.url))
    for item in _items(report, "baidu")[:5]:
        tit = item.title
        all_items.append((item.score, "百度", (tit[:50] + "...") if len(tit) > 50 else tit, item.url))
    for item in _items(report, "toutiao")[:5]:
        title = getattr(item, "title", "")
        all_items.append((item.score, "头条", (title[:50] + "...") if len(title) > 50 else title, item.url))

    all_items.sort(key=lambda x: -x[0])
    for score, source, text, url in all_items[:7]:
        lines.append(f"- [{source}] {text}")

    lines.extend(["", "## 摘要", "", "*完整报告含最佳实践、提示词包与详细来源。*", ""])
    return "\n".join(lines)


def render_full_report(report: schema.Report) -> str:
    """Render full markdown report (Chinese sections)."""
    lines = [
        _engine_badge(report),
        "",
        f"# {report.topic} — 近 30 天研究报告",
        "",
        f"**生成时间:** {report.generated_at}",
        f"**日期范围:** {report.range_from} ~ {report.range_to}",
        f"**模式:** {report.mode}",
        "",
    ]

    lines.extend(_clusters_md_lines(report))

    wb = _items(report, "weibo")
    if wb:
        lines.extend(["## 微博动态", ""])
        for item in wb:
            lines.append(f"### {item.id}: @{item.author_handle}")
            lines.append("")
            lines.append(f"- **链接:** {item.url}")
            lines.append(f"- **日期:** {item.date or '未知'} (置信: {getattr(item, 'date_confidence', 'low')})")
            lines.append(f"- **得分:** {item.score}/100")
            lines.append(f"- **相关性:** {item.why_relevant}")
            if item.engagement:
                eng = item.engagement
                c = eng.num_comments if eng.num_comments is not None else getattr(eng, "replies", "?")
                lines.append(f"- **互动:** {eng.likes or '?'} 点赞, {eng.reposts or '?'} 转发, {c} 评论")
            lines.append("")
            lines.append(f"> {getattr(item, 'text', '')}")
            lines.append("")

    xhs = _items(report, "xiaohongshu")
    if xhs:
        lines.extend(["## 小红书笔记", ""])
        for item in xhs:
            auth = getattr(item, "author_name", "") or getattr(item, "author_handle", "")
            lines.append(f"### {item.id}: {auth}")
            lines.append("")
            lines.append(f"- **链接:** {item.url}")
            lines.append(f"- **日期:** {item.date or '未知'}")
            lines.append(f"- **得分:** {item.score}/100")
            if getattr(item, "hashtags", None):
                lines.append(f"- **话题:** {' '.join('#' + h for h in item.hashtags[:10])}")
            lines.append(f"- **相关性:** {item.why_relevant}")
            lines.append("")
            body = getattr(item, "text", None) or getattr(item, "title", "")
            lines.append(f"> {body[:400]}")
            lines.append("")

    bl = _items(report, "bilibili")
    if bl:
        lines.extend(["## B站视频", ""])
        for item in bl:
            lines.append(f"### {item.id}: {item.title}")
            lines.append("")
            lines.append(f"- **UP主:** {item.channel_name}")
            lines.append(f"- **链接:** {item.url}")
            lines.append(f"- **日期:** {item.date or '未知'}")
            lines.append(f"- **得分:** {item.score}/100")
            lines.append(f"- **相关性:** {item.why_relevant}")
            if item.engagement:
                eng = item.engagement
                dm = getattr(eng, "danmaku", getattr(eng, "danmu", "?"))
                lines.append(f"- **数据:** {eng.views or '?'} 播放, {dm} 弹幕")
            lines.append("")

    zh = _items(report, "zhihu")
    if zh:
        lines.extend(["## 知乎问答", ""])
        for item in zh:
            lines.append(f"### {item.id}: {item.title}")
            lines.append("")
            zurl = getattr(item, "zhihu_url", None) or item.url
            lines.append(f"- **作者:** {getattr(item, 'author', '')}")
            lines.append(f"- **链接:** {zurl}")
            lines.append(f"- **日期:** {item.date or '未知'}")
            lines.append(f"- **得分:** {item.score}/100")
            lines.append(f"- **相关性:** {item.why_relevant}")
            if item.engagement:
                eng = item.engagement
                lines.append(f"- **互动:** {eng.score or '?'} 赞同, {eng.num_comments or '?'} 评论")
            lines.append("")

    dy = _items(report, "douyin")
    if dy:
        lines.extend(["## 抖音视频", ""])
        for item in dy:
            lines.append(f"### {item.id}: @{getattr(item, 'author_name', '')}")
            lines.append("")
            lines.append(f"- **链接:** {item.url}")
            lines.append(f"- **日期:** {item.date or '未知'}")
            lines.append(f"- **得分:** {item.score}/100")
            lines.append(f"- **相关性:** {item.why_relevant}")
            lines.append("")
            lines.append(f"> {getattr(item, 'text', '')[:300]}")
            lines.append("")

    wx = _items(report, "wechat")
    if wx:
        lines.extend(["## 微信公众号文章", ""])
        for item in wx:
            lines.append(f"### {item.id}: {item.title}")
            lines.append("")
            acct = getattr(item, "account_name", None) or getattr(item, "author_name", "")
            lines.append(f"- **公众号:** {acct}")
            lines.append(f"- **链接:** {item.url}")
            lines.append(f"- **日期:** {item.date or '未知'}")
            lines.append(f"- **得分:** {item.score}/100")
            lines.append(f"- **相关性:** {item.why_relevant}")
            sn = getattr(item, "snippet", "")
            if sn:
                lines.extend(["", f"> {sn}"])
            lines.append("")

    bd = _items(report, "baidu")
    if bd:
        lines.extend(["## 百度搜索结果", ""])
        for item in bd:
            lines.append(f"### {item.id}: {item.title}")
            lines.append("")
            lines.append(f"- **站点:** {item.source_domain}")
            lines.append(f"- **链接:** {item.url}")
            lines.append(f"- **日期:** {item.date or '未知'} (置信: {item.date_confidence})")
            lines.append(f"- **得分:** {item.score}/100")
            lines.append(f"- **相关性:** {item.why_relevant}")
            lines.append("")
            lines.append(f"> {item.snippet}")
            lines.append("")

    tt = _items(report, "toutiao")
    if tt:
        lines.extend(["## 今日头条资讯", ""])
        for item in tt:
            title = getattr(item, "title", "")
            lines.append(f"### {item.id}: {title}")
            lines.append("")
            lines.append(f"- **链接:** {item.url}")
            lines.append(f"- **日期:** {getattr(item, 'date', None) or '未知'}")
            lines.append(f"- **得分:** {item.score}/100")
            lines.append(f"- **相关性:** {getattr(item, 'why_relevant', '')}")
            lines.append("")

    lines.extend(
        [
            "## 最佳实践",
            "",
            "*由助手归纳*",
            "",
            "## 提示词包",
            "",
            "*由助手归纳*",
            "",
        ]
    )
    return "\n".join(lines)


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


SOURCE_META = {
    "weibo": ("微博", "WEIBO"),
    "xiaohongshu": ("小红书", "XHS"),
    "bilibili": ("B站", "BILI"),
    "zhihu": ("知乎", "ZHIHU"),
    "douyin": ("抖音", "DOUYIN"),
    "wechat": ("微信", "WECHAT"),
    "baidu": ("百度", "BAIDU"),
    "toutiao": ("头条", "TOUTIAO"),
}


def _plain_text(item) -> str:
    for attr in ("title", "text", "snippet", "abstract", "excerpt", "desc", "description"):
        value = getattr(item, attr, None)
        if value:
            return str(value)
    return ""


def _item_author(item) -> str:
    for attr in ("author_name", "author_handle", "channel_name", "author", "source_name", "source_domain"):
        value = getattr(item, attr, None)
        if value:
            return str(value)
    return ""


def _engagement_total(item) -> int:
    eng = getattr(item, "engagement", None)
    if not eng:
        return 0
    total = 0
    for attr in ("views", "likes", "reposts", "shares", "collects", "favorites", "num_comments", "replies", "reads", "danmaku", "voteups", "score"):
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
    source_counts = {}
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
                replace_source, replace_item = selected[idx]
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


def render_html_report(report: schema.Report) -> str:
    """Render a Guizang-inspired Swiss/IKB HTML report."""
    ranked = _collect_ranked_items(report)
    total = sum(len(_items(report, source)) for source in SOURCE_META)
    active_sources = [(source, len(_items(report, source))) for source in SOURCE_META if _items(report, source)]
    top_score = getattr(ranked[0][1], "score", 0) if ranked else 0
    freshness = _assess_data_freshness(report)
    generated = escape(report.generated_at[:19].replace("T", " "))

    source_cards = []
    for source, label in SOURCE_META.items():
        cn, code = label
        count = len(_items(report, source))
        err = _err(report, f"{source}_error")
        state = "ERROR" if err else ("ACTIVE" if count else "IDLE")
        source_cards.append(
            f'<div class="source-card"><div class="source-code">{escape(code)}</div>'
            f'<div class="source-name">{escape(cn)}</div><div class="source-count">{count}</div>'
            f'<div class="source-state">{escape(state)}</div></div>'
        )

    item_cards = []
    for idx, (source, item) in enumerate(ranked, start=1):
        cn, code = SOURCE_META[source]
        text = _plain_text(item)
        snippet = text[:220] + ("..." if len(text) > 220 else "")
        author = _item_author(item)
        date = getattr(item, "date", None) or "日期未知"
        score_value = getattr(item, "score", 0)
        reason = getattr(item, "why_relevant", "") or ""
        url = getattr(item, "url", "") or "#"
        item_cards.append(
            '<article class="item-card">'
            f'<div class="item-index">{idx:02d}</div>'
            '<div class="item-main">'
            f'<div class="item-meta"><span>{escape(code)}</span><span>{escape(date)}</span><span>{escape(author)}</span></div>'
            f'<h3>{escape(snippet or url)}</h3>'
            f'<p>{escape(reason)}</p>'
            f'<a href="{escape(_safe_href(url), quote=True)}" target="_blank" rel="noopener noreferrer">{escape(url)}</a>'
            '</div>'
            f'<div class="item-score"><span>{score_value}</span><small>SCORE</small></div>'
            '</article>'
        )

    source_summary = ", ".join(f"{SOURCE_META[s][0]} {n}" for s, n in active_sources) or "暂无可用来源"
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
                f'<div class="item-score"><span>{c.get("size", 0)}</span><small>SOURCES</small></div>'
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
<title>{escape(report.topic)} - last30days-cn</title>
<style>
:root {{
  --paper:#fafaf8; --ink:#0a0a0a; --muted:#666; --line:#d8d8d4;
  --accent:#002FA7; --accent-bright:#5B7BFF; --grey:#f0f0ee;
  --sans: Inter, "Helvetica Neue", Arial, "PingFang SC", "Microsoft YaHei", sans-serif;
  --mono: "JetBrains Mono", "SF Mono", Consolas, monospace;
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--paper); color:var(--ink); font-family:var(--sans); }}
.page {{ min-height:100vh; }}
.hero {{ min-height:72vh; padding:48px clamp(24px,5vw,72px); display:grid; grid-template-columns:7fr 5fr; gap:40px; align-items:end; background:linear-gradient(90deg, rgba(0,47,167,.08), transparent 42%), var(--paper); }}
.kicker,.meta,.source-code,.source-state,.item-meta,.item-index,.item-score small,.footer {{ font-family:var(--mono); letter-spacing:.14em; text-transform:uppercase; }}
.kicker {{ color:var(--accent); font-weight:700; margin-bottom:24px; }}
h1 {{ font-size:clamp(48px,9vw,136px); line-height:.92; letter-spacing:-.02em; margin:0; font-weight:200; }}
.hero-copy {{ max-width:760px; font-size:clamp(18px,2vw,28px); line-height:1.35; color:#333; margin-top:28px; }}
.metrics {{ display:grid; grid-template-columns:repeat(2,1fr); gap:16px; }}
.metric {{ border-top:2px solid var(--ink); padding-top:16px; min-height:136px; }}
.metric strong {{ display:block; font-size:clamp(52px,8vw,112px); line-height:.85; letter-spacing:-.04em; }}
.metric span {{ display:block; color:var(--muted); margin-top:12px; }}
.band {{ padding:36px clamp(24px,5vw,72px); background:var(--accent); color:white; display:flex; justify-content:space-between; gap:24px; flex-wrap:wrap; }}
.band strong {{ font-size:clamp(24px,4vw,56px); font-weight:300; letter-spacing:-.02em; }}
.section {{ padding:56px clamp(24px,5vw,72px); }}
.section-title {{ display:flex; justify-content:space-between; gap:24px; align-items:end; border-bottom:1px solid var(--line); padding-bottom:16px; margin-bottom:24px; }}
.section-title h2 {{ font-size:clamp(30px,5vw,72px); line-height:1; font-weight:250; margin:0; letter-spacing:-.02em; }}
.sources {{ display:grid; grid-template-columns:repeat(4,1fr); gap:1px; background:var(--line); border:1px solid var(--line); }}
.source-card {{ background:var(--paper); padding:20px; min-height:148px; display:flex; flex-direction:column; }}
.source-code,.source-state {{ color:var(--muted); font-size:12px; }}
.source-name {{ margin-top:18px; font-size:22px; }}
.source-count {{ margin-top:auto; font-size:56px; line-height:.9; font-weight:800; letter-spacing:-.04em; }}
.notice {{ margin:0 clamp(24px,5vw,72px); padding:18px 22px; background:#fff4c2; border-left:4px solid #c18b00; }}
.items {{ display:flex; flex-direction:column; border-top:1px solid var(--line); }}
.item-card {{ display:grid; grid-template-columns:72px minmax(0,1fr) 120px; gap:24px; padding:24px 0; border-bottom:1px solid var(--line); }}
.item-index {{ color:var(--accent); font-size:14px; padding-top:6px; }}
.item-meta {{ display:flex; gap:14px; flex-wrap:wrap; color:var(--muted); font-size:12px; margin-bottom:10px; }}
.item-main h3 {{ margin:0; font-size:clamp(20px,2.5vw,34px); line-height:1.2; font-weight:500; }}
.item-main p {{ color:#454545; line-height:1.55; margin:12px 0; }}
.item-main a {{ color:var(--accent); overflow-wrap:anywhere; text-decoration:none; border-bottom:1px solid rgba(0,47,167,.35); }}
.item-score {{ text-align:right; color:var(--accent); }}
.item-score span {{ display:block; font-size:56px; line-height:.9; font-weight:800; letter-spacing:-.04em; }}
.footer {{ padding:32px clamp(24px,5vw,72px); color:var(--muted); border-top:1px solid var(--line); }}
@media (max-width:900px) {{
  .hero {{ grid-template-columns:1fr; min-height:auto; }}
  .metrics,.sources {{ grid-template-columns:repeat(2,1fr); }}
  .item-card {{ grid-template-columns:44px minmax(0,1fr); }}
  .item-score {{ grid-column:2; text-align:left; }}
}}
@media print {{
  .hero {{ min-height:auto; }}
  .item-card {{ break-inside:avoid; }}
  a {{ color:var(--ink); }}
}}
</style>
</head>
<body>
<main class="page">
  <section class="hero">
    <div>
      <div class="kicker">LAST30DAYS-CN / GUIZANG SWISS REPORT</div>
      <h1>{escape(report.topic)}</h1>
      <p class="hero-copy">覆盖 {escape(report.range_from)} 至 {escape(report.range_to)} 的中文平台近况。视觉样式参考 guizang-ppt-skill 的 Swiss/IKB 报告语言，适合直接浏览、归档或打印。</p>
    </div>
    <div class="metrics">
      <div class="metric"><strong>{total}</strong><span>归一化结果</span></div>
      <div class="metric"><strong>{len(active_sources)}</strong><span>活跃平台</span></div>
      <div class="metric"><strong>{top_score}</strong><span>最高相关分</span></div>
      <div class="metric"><strong>{freshness["total_recent"]}</strong><span>近期可确认</span></div>
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
