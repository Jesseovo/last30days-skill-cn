"""Output rendering for Chinese-platform research (last30days CN skill).

Author: Jesse (https://github.com/ChiTing111)
"""

import json
import os
import tempfile
from pathlib import Path

from . import schema

OUTPUT_DIR = Path.home() / ".local" / "share" / "last30days" / "out"


def _items(report: schema.Report, name: str):
    return getattr(report, name, None) or []


def _err(report: schema.Report, name: str):
    return getattr(report, name, None)


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


def render_compact(report: schema.Report, limit: int = 15, missing_keys: str = "none") -> str:
    """Render compact output for the assistant to synthesize."""
    lines = []

    lines.append(f"## 研究结果: {report.topic}")
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
            eng_str = _fmt_eng_wechat(item.engagement)
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
        f"# {report.topic} — 近 30 天研究报告",
        "",
        f"**生成时间:** {report.generated_at}",
        f"**日期范围:** {report.range_from} ~ {report.range_to}",
        f"**模式:** {report.mode}",
        "",
    ]

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
    """Write report.json, report.md, and last30days.context.md."""
    ensure_output_dir()

    with open(OUTPUT_DIR / "report.json", "w", encoding="utf-8") as f:
        json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)

    with open(OUTPUT_DIR / "report.md", "w", encoding="utf-8") as f:
        f.write(render_full_report(report))

    with open(OUTPUT_DIR / "last30days.context.md", "w", encoding="utf-8") as f:
        f.write(render_context_snippet(report))


def get_context_path() -> str:
    """Get path to context file."""
    return str(OUTPUT_DIR / "last30days.context.md")
