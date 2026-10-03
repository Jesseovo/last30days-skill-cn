"""微博搜索模块 - 搜索微博热门内容。

Author: Jesse (https://github.com/Jesseovo)

2025 年起微博搜索（m.weibo.cn / s.weibo.com）对匿名访客返回
``{"ok": -100}``（跳转登录）。v4 的数据路径：

1. 微博开放平台 API（``WEIBO_ACCESS_TOKEN``）。
2. 移动端搜索接口 + 登录 Cookie（``WEIBO_COOKIE``，或 ``login weibo`` 保存的浏览器登录态）。
3. Playwright 浏览器爬虫（复用 ``login weibo`` 的登录态）。
4. 匿名访客 Cookie 尝试（若平台放开匿名搜索仍可用）。
5. 微博热搜榜中与主题相关的话题（无需登录）。
6. ``site:weibo.com`` 公开搜索兜底（经 URL 与相关性校验）。

所有路径失败时会明确说明「微博搜索需要登录」以及修复命令，而不是静默 0 条。
"""

import re
import sys
import urllib.parse
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from . import dates, http, relevance, websearch

MOBILE_SEARCH_URL = "https://m.weibo.cn/api/container/getIndex"
HOT_SEARCH_URL = "https://weibo.com/ajax/side/hotSearch"
VISITOR_URL = "https://passport.weibo.com/visitor/genvisitor2"
STATUS_URL_PATTERN = r"(?:weibo\.com/\d+/[A-Za-z0-9]{6,}|m\.weibo\.cn/(?:status|detail)/\w+)"

LOGIN_HINT = (
    "微博搜索现需登录：运行 `python scripts/last30days.py login weibo`（需 Playwright）"
    "保存登录态，或在 ~/.config/last30days-cn/.env 配置 WEIBO_COOKIE"
)


class WeiboLoginRequired(Exception):
    """m.weibo.cn answered ok=-100 (redirect to login)."""


def search_weibo(
    topic: str,
    from_date: str,
    to_date: str,
    depth: str = "default",
    token: Optional[str] = None,
    cookie: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """搜索微博内容。

    Args:
        topic: 搜索关键词
        from_date: 起始日期 YYYY-MM-DD
        to_date: 结束日期 YYYY-MM-DD
        depth: 搜索深度 quick/default/deep
        token: 微博 access_token（可选）
        cookie: 已登录的 m.weibo.cn Cookie（可选，WEIBO_COOKIE）

    Returns:
        微博条目列表，每条包含 id, text, url, author_handle, date,
        engagement, relevance, why_relevant 等字段
    """
    limit_map = {"quick": 15, "default": 30, "deep": 50}
    limit = limit_map.get(depth, 30)
    pages = {"quick": 1, "default": 2, "deep": 3}.get(depth, 2)

    items: List[Dict[str, Any]] = []
    login_required = False

    if token:
        items = _search_via_api(topic, limit, token)

    if not items and cookie:
        try:
            items = _search_via_mobile(topic, pages, cookie=cookie)
            if items:
                sys.stderr.write(f"[微博] 使用 WEIBO_COOKIE 获取 {len(items)} 条结果\n")
        except WeiboLoginRequired:
            login_required = True
            sys.stderr.write("[微博] WEIBO_COOKIE 已失效（接口要求重新登录）\n")
        except Exception as e:
            sys.stderr.write(f"[微博] Cookie 搜索失败: {e}\n")

    if not items:
        try:
            from . import crawler_bridge
            if crawler_bridge.is_playwright_available():
                sys.stderr.write("[微博] 尝试浏览器爬虫模式...\n")
                items = crawler_bridge.crawl_weibo(topic, limit)
                if items:
                    sys.stderr.write(f"[微博] 爬虫模式获取 {len(items)} 条结果\n")
                elif not crawler_bridge.has_login("weibo"):
                    login_required = True
        except Exception as e:
            sys.stderr.write(f"[微博] 爬虫模式失败: {e}\n")

    if not items and not cookie:
        try:
            items = _search_via_mobile(topic, 1, cookie=None)
        except WeiboLoginRequired:
            login_required = True
        except Exception as e:
            http.log(f"[微博] 匿名接口失败: {e}")

    if not items:
        hot = _search_hot_related(topic)
        site = _search_via_site_search(topic, limit)
        items = hot + site
        if items:
            sys.stderr.write(
                f"[微博] 原生搜索不可用，已用热搜榜/公开搜索兜底获取 {len(items)} 条"
                f"（热搜 {len(hot)}，公开链接 {len(site)}）。\n"
            )

    if not items and login_required:
        raise http.HTTPError(LOGIN_HINT)

    scored = []
    for item in items:
        text = item.get("text", "")
        if "relevance" not in item:
            item["relevance"] = relevance.token_overlap_relevance(topic, text)
        item.setdefault("why_relevant", f"微博讨论：{text[:60]}")
        scored.append(item)

    scored.sort(key=lambda x: x.get("relevance", 0), reverse=True)
    scored = scored[:limit]
    for i, item in enumerate(scored):
        item["id"] = f"WB{i+1}"
    return scored


def _search_via_api(topic: str, limit: int, token: str) -> List[Dict[str, Any]]:
    """通过微博开放平台 API 搜索。"""
    items = []
    try:
        encoded = urllib.parse.quote(topic)
        url = (
            f"https://api.weibo.com/2/search/statuses.json"
            f"?access_token={token}&q={encoded}&count={min(limit, 50)}"
        )
        resp = http.get(url, timeout=15, retries=2)
        if isinstance(resp, dict) and "statuses" in resp:
            for s in resp["statuses"]:
                items.append(_parse_status(s))
    except Exception as e:
        sys.stderr.write(f"[微博] API 搜索失败: {e}\n")
    return items


def _mobile_session(cookie: Optional[str]) -> http.Session:
    session = http.Session(http.browser_headers(kind="mobile", referer="https://m.weibo.cn/", accept="json"))
    session.headers["X-Requested-With"] = "XMLHttpRequest"
    if cookie:
        session.load_cookie_header(cookie, ".weibo.cn")
        session.load_cookie_header(cookie, ".weibo.com")
    else:
        _attach_visitor_cookie(session)
    return session


def _attach_visitor_cookie(session: http.Session) -> None:
    """Obtain anonymous SUB/SUBP visitor cookies (cheap; may not unlock search)."""
    try:
        body = session.post_form(
            VISITOR_URL,
            {"cb": "visitor_gray_callback", "tid": "", "from": "weibo"},
            headers={"Referer": "https://passport.weibo.com/visitor/visitor"},
            timeout=8,
        )
        for name in ("sub", "subp"):
            match = re.search(rf'"{name}":"([^"]+)"', body or "")
            if match:
                value = match.group(1)
                session.set_cookie(name.upper(), value, ".weibo.cn")
                session.set_cookie(name.upper(), value, ".weibo.com")
    except Exception as exc:
        http.log(f"[微博] 访客 Cookie 获取失败: {exc}")


def _search_via_mobile(topic: str, pages: int, cookie: Optional[str]) -> List[Dict[str, Any]]:
    """移动端搜索接口（需要登录 Cookie；匿名时通常返回 ok=-100）。"""
    session = _mobile_session(cookie)
    containerid = f"100103type=1&q={topic}"
    items: List[Dict[str, Any]] = []
    for page in range(1, pages + 1):
        params = {"containerid": containerid, "page_type": "searchall"}
        if page > 1:
            params["page"] = str(page)
        data = session.get_json(f"{MOBILE_SEARCH_URL}?{urllib.parse.urlencode(params)}", timeout=15)
        if not isinstance(data, dict):
            break
        if data.get("ok") == -100 or "passport.weibo.com" in str(data.get("url", "")):
            raise WeiboLoginRequired()
        page_items = parse_mobile_cards(data)
        items.extend(page_items)
        if not page_items:
            break
    return items


def parse_mobile_cards(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract mblogs from an m.weibo.cn ``getIndex`` payload."""
    items = []
    for card in ((data.get("data") or {}).get("cards") or []):
        if card.get("card_type") == 9 and card.get("mblog"):
            items.append(_parse_mblog(card["mblog"]))
        for group in card.get("card_group") or []:
            if isinstance(group, dict) and group.get("mblog"):
                items.append(_parse_mblog(group["mblog"]))
    return items


def fetch_hot(limit: int = 50) -> List[Dict[str, Any]]:
    """微博热搜榜（无需登录）。"""
    data = http.get(
        HOT_SEARCH_URL,
        headers=http.browser_headers(referer="https://weibo.com/", accept="json"),
        timeout=10,
        retries=1,
    )
    out = []
    for entry in ((data or {}).get("data") or {}).get("realtime") or []:
        if entry.get("is_ad"):
            continue
        word = entry.get("word") or entry.get("note") or ""
        if not word:
            continue
        query = entry.get("word_scheme") or f"#{word}#"
        out.append({
            "rank": entry.get("realpos") or (entry.get("rank", len(out)) + 1),
            "title": word,
            "url": f"https://s.weibo.com/weibo?q={urllib.parse.quote(query)}",
            "hot_value": entry.get("num"),
            "label": entry.get("label_name") or "",
        })
        if len(out) >= limit:
            break
    return out


def _search_hot_related(topic: str) -> List[Dict[str, Any]]:
    try:
        hot = fetch_hot(50)
    except Exception as exc:
        http.log(f"[微博] 热搜榜获取失败: {exc}")
        return []
    today = datetime.now(dates.CST).strftime("%Y-%m-%d")
    items = []
    for entry in hot:
        rel = relevance.token_overlap_relevance(topic, entry["title"])
        if rel < 0.35:
            continue
        label = f"「{entry['label']}」" if entry.get("label") else ""
        items.append({
            "text": f"#{entry['title']}#",
            "url": entry["url"],
            "author_handle": "微博热搜",
            "author_id": "",
            "date": today,
            "engagement": None,
            "relevance": rel,
            "why_relevant": f"微博热搜第 {entry['rank']} 位{label}，热度 {entry.get('hot_value') or '未知'}",
            "source": "hot-search",
        })
    return items


def _search_via_site_search(topic: str, limit: int) -> List[Dict[str, Any]]:
    items = []
    for result in websearch.site_search(
        ["weibo.com", "m.weibo.cn"], topic, limit=min(limit, 10), url_pattern=STATUS_URL_PATTERN, label="微博"
    ):
        text = f"{result.title} {result.snippet}".strip()
        items.append({
            "text": text,
            "url": result.url,
            "author_handle": "",
            "author_id": "",
            "date": result.date,
            "engagement": None,
            "source": f"site-search:{result.engine}",
            "why_relevant": f"微博公开链接（{result.engine} 搜索兜底）：{result.title[:40]}",
        })
    return items


def _parse_status(s: dict) -> Dict[str, Any]:
    """解析微博开放平台 API 返回的状态。"""
    text = _clean_html(s.get("text", ""))
    user = s.get("user", {}) or {}
    return {
        "text": text,
        "url": f"https://weibo.com/{user.get('id', '')}/{s.get('mid', '')}",
        "author_handle": user.get("screen_name", ""),
        "author_id": str(user.get("id", "")),
        "date": _parse_weibo_date(s.get("created_at", "")),
        "engagement": {
            "reposts": s.get("reposts_count", 0),
            "comments": s.get("comments_count", 0),
            "likes": s.get("attitudes_count", 0),
        },
        "source": "open-api",
    }


def _parse_mblog(mblog: dict) -> Dict[str, Any]:
    """解析微博移动端接口返回的 mblog。"""
    text = _clean_html(mblog.get("text", ""))
    user = mblog.get("user", {}) or {}
    mid = mblog.get("mid", "") or mblog.get("id", "")
    bid = mblog.get("bid") or mid
    return {
        "text": text,
        "url": f"https://weibo.com/{user.get('id', '')}/{bid}",
        "author_handle": user.get("screen_name", ""),
        "author_id": str(user.get("id", "")),
        "date": _parse_weibo_date(mblog.get("created_at", "")),
        "engagement": {
            "reposts": _to_int(mblog.get("reposts_count")),
            "comments": _to_int(mblog.get("comments_count")),
            "likes": _to_int(mblog.get("attitudes_count")),
        },
        "source": "mobile-api",
    }


def _to_int(value: Any) -> int:
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value or "").strip()
    try:
        if text.endswith("万"):
            return int(float(text[:-1]) * 10000)
        return int(float(text or 0))
    except ValueError:
        return 0


def _clean_html(text: str) -> str:
    """清除微博文本中的 HTML 标签。"""
    text = re.sub(r"<[^>]+>", "", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _parse_weibo_date(date_str: str) -> Optional[str]:
    """将微博日期格式转换为 YYYY-MM-DD（北京时间）。"""
    if not date_str:
        return None
    date_str = str(date_str).strip()
    try:
        # "Tue Jan 01 00:00:00 +0800 2026"
        dt = datetime.strptime(date_str, "%a %b %d %H:%M:%S %z %Y")
        return dt.astimezone(dates.CST).strftime("%Y-%m-%d")
    except ValueError:
        pass
    now = datetime.now(dates.CST)
    if "刚刚" in date_str:
        return now.strftime("%Y-%m-%d")
    match = re.search(r"(\d+)\s*分钟前", date_str)
    if match:
        return (now - timedelta(minutes=int(match.group(1)))).strftime("%Y-%m-%d")
    match = re.search(r"(\d+)\s*小时前", date_str)
    if match:
        return (now - timedelta(hours=int(match.group(1)))).strftime("%Y-%m-%d")
    if "前天" in date_str:
        return (now - timedelta(days=2)).strftime("%Y-%m-%d")
    if "昨天" in date_str:
        return (now - timedelta(days=1)).strftime("%Y-%m-%d")
    match = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", date_str)
    if match:
        return f"{int(match.group(1)):04d}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
    match = re.match(r"(\d{1,2})-(\d{1,2})", date_str)
    if match:
        month, day = int(match.group(1)), int(match.group(2))
        year = now.year if (month, day) <= (now.month, now.day) else now.year - 1
        return f"{year:04d}-{month:02d}-{day:02d}"
    return None
