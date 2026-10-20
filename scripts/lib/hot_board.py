"""Self-contained hot-board page, with progressive search and compact source cards.

The small cat sprite is adapted from Jesseovo/Jesseovo's user-supplied, redrawn
profile artwork (scripts/animate_cat.py). Each pose uses the original pixel grid;
CSS moves whole sprites without rotating or deforming them. No runtime imaging
library, network asset, font service or frontend dependency is required.
"""

import base64
from html import escape
from pathlib import Path
from typing import Any, Callable, Dict

_ASSETS = Path(__file__).resolve().parent
_LINK = 'target="_blank" rel="noopener noreferrer"'
_ICONS = {
    "search": '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4 4"/>',
    "close": '<path d="m6 6 12 12M6 18 18 6"/>',
    "chevron": '<path d="m6 9 6 6 6-6"/>',
    "arrow": '<path d="M5 12h14m-5-5 5 5-5 5"/>',
    "external": '<path d="M14 4h6v6m0-6L10 14M10 4H5a1 1 0 0 0-1 1v14a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-5"/>',
    "layers": '<path d="m12 3 9 5-9 5-9-5 9-5ZM3 12l9 5 9-5M3 16l9 5 9-5"/>',
    "grid": '<rect x="3" y="3" width="6" height="6" rx="1"/><rect x="15" y="3" width="6" height="6" rx="1"/><rect x="3" y="15" width="6" height="6" rx="1"/><rect x="15" y="15" width="6" height="6" rx="1"/>',
    "moon": '<path d="M20.5 13A8.5 8.5 0 0 1 11 3.5 8.5 8.5 0 1 0 20.5 13Z"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5"/>',
    "github": '<path d="M9 19c-4 1-4-2-6-2m12 5v-4a3.5 3.5 0 0 0-1-2.5c3.4-.4 7-1.6 7-7.5a5.8 5.8 0 0 0-1.6-4A5.4 5.4 0 0 0 19 0s-1.3-.4-4 1.5a14 14 0 0 0-7 0C5.3-.4 4 0 4 0a5.4 5.4 0 0 0-.4 4A5.8 5.8 0 0 0 2 8c0 5.9 3.6 7.1 7 7.5A3.5 3.5 0 0 0 8 18v4" transform="translate(1 1) scale(.9)"/>',
    "tv": '<rect x="3" y="6" width="18" height="15" rx="3"/><path d="m8 2 4 4 4-4M8 12v3m8-3v3m-6 2h4"/>',
    "music": '<path d="M14 3v12a4 4 0 1 1-4-4m4-8c0 4 3 6 7 6"/>',
    "rss": '<path d="M5 11a8 8 0 0 1 8 8M5 4a15 15 0 0 1 15 15"/><circle cx="5" cy="19" r="1" fill="currentColor"/>',
    "spark": '<path d="m12 3 2.3 6.7L21 12l-6.7 2.3L12 21l-2.3-6.7L3 12l6.7-2.3L12 3Z"/>',
    "star": '<path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2-5.6-3-5.6 3 1.1-6.2L3 9.6l6.2-.9L12 3Z"/>',
}

# Fixed presentation values only; source-provided identifiers never become CSS.
_PLATFORMS = {
    "weibo": ("#c7694f", "#fbefe6", "微"),
    "baidu": ("#6175b5", "#edf0fa", "百"),
    "douyin": ("#646377", "#f0eff6", "music"),
    "toutiao": ("#bf6266", "#fbecee", "头"),
    "bilibili": ("#7197ab", "#eaf3f7", "tv"),
    "zhihu": ("#528cbb", "#eaf2fa", "知"),
    "ithome": ("#ba685e", "#fbefeb", "IT"),
    "huxiu": ("#8a8153", "#f5f2e6", "虎"),
    "sspai": ("#b56c62", "#f9eeea", "π"),
    "ifanr": ("#6b817c", "#edf3f0", "A"),
    "solidot": ("#879465", "#f0f3e8", "S"),
    "hackernews": ("#b77c49", "#fbf0e3", "Y"),
}


def _icon(name: str, extra: str = "") -> str:
    return (
        '<svg class="icon ' + extra + '" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="1.6" stroke-linecap="round" '
        'stroke-linejoin="round" aria-hidden="true">' + _ICONS[name] + '</svg>'
    )


def _text(value: Any) -> str:
    return escape(str(value), quote=True)


def _group(sid: str, board: Dict[str, Any]) -> str:
    if sid == "hackernews":
        return "global"
    return "news" if board.get("kind") == "feed" else "cn"


_BRAND = '''<svg class="brand-icon" viewBox="0 0 28 28" fill="currentColor" aria-hidden="true" shape-rendering="crispEdges">
<path d="M6 2h3v4h10V2h3v4h4v20H2V6h4z" opacity=".18"/>
<path d="M6 2h3v6H6zm13 0h3v6h-3zM2 6h4v3H5v14h18V9h-1V6h4v20H2zM5 10h18v3H5zM8 16h4v4H8zm8 0h4v4h-4z"/></svg>'''

_DESK = '''<div class="hero-art" aria-hidden="true">
<div class="art-grid"></div>
<svg class="pixel-desk" viewBox="0 0 102 66" shape-rendering="crispEdges">
<path d="M6 59h90v2H6zM12 61h6v3h-6zm70 0h6v3h-6z" fill="#d4decf"/>
<path d="M15 13h39v2h2v29H13V15h2z" fill="#7c9489"/>
<path d="M16 16h37v24H16z" fill="#d0dfce"/>
<path d="M18 18h33v20H18z" fill="#344f48"/>
<path d="M22 23h3v2h-3zm3 2h3v2h-3zm-3 2h3v2h-3zM31 27h12v2H31z" fill="#b8d2b3"/>
<path class="pixel-ping" d="M31 32h3v2h-3z" fill="#d8b8a1"/>
<path d="M18 42h2v1h-2zm12 2h10v7H30zm-8 7h26v3H22z" fill="#7c9489"/>
<path d="M19 55h35v3H19zM17 58h39v1H17z" fill="#aebfac"/>
<path d="M21 55h2v1h-2zm5 0h2v1h-2zm5 0h2v1h-2zm5 0h2v1h-2zm5 0h2v1h-2z" fill="#dce5d6"/>
<path d="M63 47h11v10H63zm11 2h4v6h-4v-2h2v-2h-2zM65 57h7v2h-7z" fill="#c9a48f"/>
<path d="M65 47h7v2h-7z" fill="#775c4b"/>
<path d="M66 39h2v5h-2zm2-4h2v4h-2z" fill="#d2dacf"/>
<path d="M65 17h15v2h2v11H63V19h2z" fill="#e2e8dc"/>
<path d="M67 21h10v2H67zm0 5h6v2h-6z" fill="#99af8d"/>
<path d="M86 9h2v4h4v2h-4v4h-2v-4h-4v-2h4z" fill="#c6b39b"/>
<path d="M7 33h2v2H7zm77 4h2v2h-2z" fill="#adbfa5"/>
</svg><div class="cat-track"><div class="pixel-cat"></div></div>
<span class="art-caption">STAY CURIOUS, KEEP EXPLORING.</span></div>'''


def render_page(data: Dict[str, Any], per_board: int, max_topics: int, site_title: str,
                fmt_hot: Callable[[Any], str], safe_href: Callable[[str], str]) -> str:
    """Render escaped source data; all controls enhance an already readable page."""
    boards = data["boards"]
    topics = data.get("topics") or []
    total = sum(len(b.get("items") or []) for b in boards.values())
    live = sum(1 for b in boards.values() if b.get("items"))
    groups = {"cn": 0, "news": 0, "global": 0}
    for sid, board in boards.items():
        groups[_group(sid, board)] += 1

    def link(url: str) -> str:
        return _text(safe_href(url))

    topic_cards = []
    for idx, topic in enumerate(topics[:max_topics], 1):
        mentions = topic.get("mentions") or []
        categories = sorted({_group(m["platform"], boards.get(m["platform"], {})) for m in mentions})
        keywords = " ".join([topic["title"]] + [m["label"] for m in mentions])
        chips = "".join(
            '<a class="chip" href="{}" {}>{}<span>#{}</span></a>'.format(
                link(m.get("url", "")), _LINK, _text(m["label"]), _text(m["rank"]))
            for m in mentions
        )
        topic_cards.append(
            '<article class="topic" data-k="{}" data-groups="{}">'
            '<div class="topic-meta"><span class="topic-number">{:02d}</span><span>{} 个平台都在聊</span></div>'
            '<a class="t" href="{}" {} title="{}">{}</a><div class="chips">{}</div></article>'.format(
                _text(keywords), _text(" ".join(categories)), idx,
                _text(topic.get("platform_count", len(mentions))), link(topic.get("url", "")),
                _LINK, _text(topic["title"]), _text(topic["title"]), chips)
        )

    board_cards = []
    source_tabs = []
    for idx, (sid, board) in enumerate(boards.items()):
        items = (board.get("items") or [])[:per_board]
        label = board.get("label") or sid
        code = board.get("code") or sid
        color, background, symbol = _PLATFORMS.get(sid, ("#698268", "#eef2e9", "rss"))
        badge = _icon(symbol) if symbol in _ICONS else _text(symbol)
        short_label = str(label).replace("热搜", "").replace("热榜", "").strip() or str(label)
        source_tabs.append(
            '<button class="source-tab" type="button" id="source-tab-{}" '
            'data-board="{}" aria-pressed="false" aria-controls="board-card-{}">'
            '<span class="platform-icon" style="--platform:{};--platform-bg:{}" aria-hidden="true">{}</span>'
            '<span class="source-tab-label">{}</span><small class="source-match" hidden></small></button>'.format(
                idx, idx, idx, color, background, badge, _text(short_label))
        )
        list_id = "board-items-{}".format(idx)
        if items:
            rows = []
            for item in items:
                is_board = board.get("kind") == "board"
                heat = fmt_hot(item.get("hot_value")) if is_board else (item.get("label") or "")
                tag = '<span class="tag">{}</span>'.format(_text(item["label"])) if is_board and item.get("label") else ""
                metadata = '<span class="story-meta"><span class="heat">{}</span>{}</span>'.format(_text(heat), tag)
                rank = item.get("rank", "")
                rank_label = "{:02d}".format(rank) if isinstance(rank, int) else str(rank)
                rows.append(
                    '<li data-k="{}"><a class="story" href="{}" {} title="{}">'
                    '<span class="rank">{}</span><span class="story-content"><span class="story-title">{}</span>{}</span></a></li>'.format(
                        _text(item["title"]), link(item.get("url", "")), _LINK, _text(item["title"]),
                        _text(rank_label), _text(item["title"]), metadata)
                )
            body = '<ol id="{}">{}</ol>'.format(list_id, "".join(rows))
            body += (
                '<button class="board-open js-only" type="button" aria-haspopup="dialog" aria-controls="board-reader" '
                'aria-label="查看{}完整榜单"><span>查看全部 {} 条</span>{}</button>'.format(
                    _text(label), len(items), _icon("arrow"))
            )
        else:
            message = str(board.get("error") or "该来源在本次快照中没有返回条目。")
            body = (
                '<div class="board-error"><p>这次暂时没有取到内容</p><details><summary>查看来源状态</summary>'
                '<p>{}</p></details></div>'.format(_text(message))
            )
        board_cards.append(
            '<article class="board" id="board-card-{}" data-group="{}" data-k="{}" data-code="{}" aria-labelledby="board-title-{}">'
            '<div class="board-head"><span class="platform-icon" style="--platform:{};--platform-bg:{}" aria-hidden="true">{}</span>'
            '<div class="board-identity"><h3 id="board-title-{}">{}</h3><span class="code">{}</span></div>'
            '<span class="board-count">{}</span></div>{}</article>'.format(
                idx, _group(sid, board), _text(label), _text(code), idx, color, background, badge,
                idx, _text(label), _text(code), "{} 条".format(len(items)) if items else "未获取", body)
        )

    topic_section = ""
    if topic_cards:
        topic_section = (
            '<section class="topics-section" id="topics-section" aria-labelledby="topics-title">'
            '<div class="section-head"><div class="section-title">{}<h2 id="topics-title">同频热点</h2>'
            '<span class="section-note">在不同平台，遇见同一个话题</span></div>'
            '<button class="text-button js-only" id="topics-toggle" type="button" aria-expanded="false" '
            'aria-controls="topics"><span>查看全部 {} 个</span>{}</button></div>'
            '<div class="topics" id="topics">{}</div></section>'.format(
                _icon("layers"), len(topic_cards), _icon("chevron"), "".join(topic_cards))
        )

    filters = '<button type="button" class="filter" data-filter="all" aria-pressed="true">全部<small>{}</small></button>'.format(len(boards))
    for category, label in (("cn", "国内热榜"), ("news", "科技资讯"), ("global", "全球视野")):
        if groups[category]:
            filters += '<button type="button" class="filter" data-filter="{}" aria-pressed="false">{}<small>{}</small></button>'.format(category, label, groups[category])

    filter_note = '<span>关键词「{}」</span>'.format(_text(data["topic_filter"])) if data.get("topic_filter") else ""
    style = (_ASSETS / "hot_board.css").read_text(encoding="utf-8")
    script = (_ASSETS / "hot_board.js").read_text(encoding="utf-8")
    sprite = base64.b64encode((_ASSETS / "hot_board_cat.png").read_bytes()).decode("ascii")
    style += '\n:root { --cat-sprite: url("data:image/png;base64,' + sprite + '"); }'
    theme_init = "try{var t=localStorage.getItem('last30days-hot-theme');if(t==='light'||t==='dark')document.documentElement.setAttribute('data-theme',t);}catch(e){}"
    return '''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<meta name="description" content="每天一点好奇心。聚合微博、百度、抖音、B站、知乎、科技资讯与 Hacker News，轻松浏览各平台热点。">
<title>{title} · {generated}</title>
<script>{theme_init}</script>
<style>{style}</style>
</head>
<body>
<a class="skip" href="#boards-section">跳到各平台榜单</a>
<div class="wrap">
<header class="nav">
  <a class="brand" href="https://github.com/Jesseovo/last30days-skill-cn" {external}>{brand}<span>last30days<span style="opacity:.45"> / </span>热榜</span></a>
  <span class="brand-note">A LITTLE CURIOSITY, EVERY DAY.</span>
  <div class="nav-actions"><a class="nav-link" href="https://github.com/Jesseovo/last30days-skill-cn" {external}>{github}GitHub</a>
    <button class="icon-button js-only" id="theme-toggle" type="button" aria-label="切换主题">{moon}{sun}</button></div>
</header>
<main>
<section class="hero" aria-label="热榜概览"><div class="hero-copy">
  <div class="eyebrow">YOUR DAILY DOSE OF DISCOVERY</div>
  <h1>{title}</h1>
  <p>今天，世界在聊什么？<span class="caret" aria-hidden="true"></span></p>
  <div class="snapshot"><span><i class="dot" aria-hidden="true"></i><time>{generated}</time> 更新 · 北京时间</span>
    <span><b>{live}</b> 个来源有内容</span><span><b>{total}</b> 条收录</span>{filter_note}</div>
</div>{desk}</section>
<div class="toolbar js-only">
  <div class="filters" role="group" aria-label="按来源分类">{filters}</div>
  <div class="search-box">{search}<input id="q" type="search" placeholder="找点感兴趣的 · AI、游戏、科技…" aria-label="搜索热点或平台" autocomplete="off">
    <button class="search-clear" id="search-clear" type="button" aria-label="清空搜索" hidden>{close}</button></div>
</div>
<noscript><p class="noscript">已展示全部条目；开启 JavaScript 可使用搜索、分类和折叠功能。</p></noscript>
{topic_section}
<section class="boards-section" id="boards-section" aria-labelledby="boards-title">
  <div class="section-head"><div class="section-title">{grid}<h2 id="boards-title">各平台榜单</h2></div>
    <span class="board-summary" id="board-summary" role="status" aria-live="polite">{board_count} 个榜单</span></div>
  <div class="source-nav js-only">
    <button class="source-toggle" id="source-toggle" type="button" aria-expanded="false" aria-controls="source-picker">
      <span class="source-current" id="source-current"></span><span class="source-toggle-action"><span id="source-toggle-label">切换平台</span>{chevron}</span>
    </button>
    <div class="source-picker" id="source-picker" hidden>
      <div class="source-picker-head"><span>选择平台</span><small id="source-picker-count"></small></div>
      <div class="source-tabs" role="group" aria-label="选择平台榜单">{source_tabs}</div>
    </div>
  </div>
  <div class="grid">{board_cards}</div>
  <div class="empty js-only" id="empty" hidden>{spark}<h2>还没找到相关热点</h2><p>换个关键词，或看看其他分类。</p><button type="button" class="reset-button" id="reset">查看全部热点</button></div>
</section>
</main>
<dialog class="board-reader" id="board-reader" aria-labelledby="reader-title" aria-describedby="reader-context">
  <header class="reader-head"><div id="reader-icon" aria-hidden="true"></div><div class="reader-identity"><div class="eyebrow">TAKE A CLOSER LOOK</div><h2 id="reader-title">完整榜单</h2></div>
    <button class="icon-button" id="reader-close" type="button" aria-label="关闭完整榜单" autofocus>{close}</button></header>
  <p class="reader-context" id="reader-context"></p>
  <ol class="reader-list" id="reader-list"></ol>
  <footer class="reader-footer">{external_icon}<span>点击条目，在新窗口查看来源</span><time>{generated} · 北京时间</time></footer>
</dialog>
<footer class="footer"><div><p>榜单为定时采集快照，排名与热度以来源页面为准。</p>
  <p>由 <a href="https://github.com/Jesseovo/last30days-skill-cn" {external}>last30days-cn</a> 生成 · 数据来自各平台公开内容</p></div>
  <div class="footer-sign">Made with curiosity <span>✦</span><br><a href="https://github.com/Jesseovo" {external}>a little corner by Jesse</a></div></footer>
</div>
<aside class="star-nudge" id="star-nudge" role="region" aria-labelledby="star-title" aria-live="polite" hidden>
  <div class="star-badge" aria-hidden="true">{star}</div>
  <div class="star-copy"><h2 id="star-title">觉得好用？点颗 Star 吧</h2><p>让更多人发现这个小小热榜。</p>
    <a class="star-link" id="star-link" href="https://github.com/Jesseovo/last30days-skill-cn" {external}>{github}<span>去 GitHub Star</span>{external_icon}</a></div>
  <button class="star-close" id="star-close" type="button" aria-label="关闭 Star 提示">{close}</button>
</aside>
<script>{script}</script>
</body>
</html>'''.format(
        title=_text(site_title), generated=_text(data["generated_at"]), theme_init=theme_init,
        style=style, external=_LINK, brand=_BRAND, github=_icon("github"), moon=_icon("moon", "theme-moon"),
        sun=_icon("sun", "theme-sun"), live=live, total=total, filter_note=filter_note, desk=_DESK,
        filters=filters, search=_icon("search"), close=_icon("close"), chevron=_icon("chevron"), external_icon=_icon("external"), topic_section=topic_section,
        grid=_icon("grid"), board_count=len(boards), board_cards="".join(board_cards), source_tabs="".join(source_tabs), spark=_icon("spark"),
        star=_icon("star"), script=script)
