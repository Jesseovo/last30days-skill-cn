"""小红书搜索模块 - 搜索小红书笔记。

Author: Jesse (https://github.com/Jesseovo)

v4 数据路径（按优先级自动切换）：
1. xiaohongshu-mcp HTTP API（自托管，可选）。修复：v3 调用的是不存在的
   ``GET /api/v1/search/notes``；xpzouying/xiaohongshu-mcp 的真实接口是
   ``POST /api/v1/feeds/search``（camelCase 的 ``noteCard``/``interactInfo``）。
   旧接口仍作为兼容回退保留。
2. Playwright 浏览器（需要 ``login xiaohongshu`` 保存的登录态；XHR 卡片 +
   ``window.__INITIAL_STATE__`` + DOM 三重解析，见 crawler_bridge）。
3. ``site:xiaohongshu.com`` 公开搜索兜底（仅接受 ``/explore/<24位笔记ID>`` 链接，
   并做主题相关性校验）。

注意：v2.1 起已移除 ScrapeCreators 集成（官方未提供小红书端点）；v4 移除了
恒返回 404 的 ``fe_api/burdock`` 公开接口。
"""

import re
import sys
import urllib.parse
from typing import Any, Dict, List, Optional

from . import dates, http, relevance, websearch

NOTE_URL_PATTERN = r"xiaohongshu\.com/(?:explore|discovery/item)/[0-9a-f]{24}"
LOGIN_HINT = (
    "小红书搜索需要登录态：运行 `python scripts/last30days.py login xiaohongshu` 扫码登录一次"
    "（需 Playwright），或部署 xiaohongshu-mcp 并配置 XIAOHONGSHU_API_BASE"
)

_SCRAPECREATORS_DEPRECATION_WARNED = False


def search_xiaohongshu(
    topic: str,
    from_date: str,
    to_date: str,
    depth: str = "default",
    token: Optional[str] = None,
    api_base: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """搜索小红书笔记。

    Args:
        topic: 搜索关键词
        from_date: 起始日期 YYYY-MM-DD
        to_date: 结束日期 YYYY-MM-DD
        depth: 搜索深度 quick/default/deep
        token: 已弃用 —— 保留参数仅为向后兼容（v2.1 移除 ScrapeCreators 集成）
        api_base: xiaohongshu-mcp 自托管 HTTP API 地址（可选）

    Returns:
        小红书笔记列表
    """
    limit_map = {"quick": 10, "default": 20, "deep": 40}
    limit = limit_map.get(depth, 20)

    if token:
        global _SCRAPECREATORS_DEPRECATION_WARNED
        if not _SCRAPECREATORS_DEPRECATION_WARNED:
            sys.stderr.write(
                "[小红书] 提示：ScrapeCreators 不提供小红书数据，SCRAPECREATORS_API_KEY 已被忽略。\n"
            )
            _SCRAPECREATORS_DEPRECATION_WARNED = True

    items: List[Dict[str, Any]] = []
    attempted: List[str] = []

    if api_base:
        attempted.append("MCP")
        items = _search_via_mcp(topic, depth, limit, api_base)

    crawler_logged_in = None
    if not items and depth != "quick":
        try:
            from . import crawler_bridge
            if crawler_bridge.is_playwright_available():
                attempted.append("Playwright")
                crawler_logged_in = crawler_bridge.has_login("xiaohongshu")
                if not crawler_logged_in:
                    sys.stderr.write(
                        "[小红书] 浏览器尚未登录小红书，搜索页通常只返回登录弹窗；"
                        "可运行 `python scripts/last30days.py login xiaohongshu`。仍尝试一次...\n"
                    )
                else:
                    sys.stderr.write("[小红书] 尝试浏览器爬虫模式（已登录）...\n")
                items = crawler_bridge.crawl_xiaohongshu(topic, limit)
                if items:
                    sys.stderr.write(f"[小红书] 爬虫模式获取 {len(items)} 条结果\n")
        except Exception as e:
            sys.stderr.write(f"[小红书] 爬虫模式失败: {e}\n")

    if not items:
        attempted.append("公开搜索")
        items = _search_via_site_search(topic, limit)

    if not items:
        reason = "已尝试：" + " / ".join(attempted) + "。"
        if crawler_logged_in is False or "Playwright" not in attempted:
            reason += LOGIN_HINT + "。"
        reason += websearch.describe_failure("小红书")
        raise http.HTTPError(reason)

    scored = []
    for item in items:
        title = item.get("title", "")
        desc = item.get("desc", "")
        rel = relevance.token_overlap_relevance(topic, f"{title} {desc}", hashtags=item.get("hashtags"))
        item["relevance"] = rel
        source = item.get("source", "xiaohongshu")
        item["why_relevant"] = f"小红书来源({source}): {title[:50]}"
        scored.append(item)

    scored.sort(key=lambda x: x.get("relevance", 0), reverse=True)
    scored = scored[:limit]
    for i, item in enumerate(scored):
        item["id"] = f"XHS{i+1}"
    return scored


def note_url(note_id: str, xsec_token: Optional[str] = None) -> str:
    """Build a note URL. Without xsec_token, XHS often refuses anonymous views."""
    if not note_id:
        return ""
    base = f"https://www.xiaohongshu.com/explore/{note_id}"
    if xsec_token:
        return f"{base}?xsec_token={urllib.parse.quote(xsec_token, safe='')}&xsec_source=pc_search"
    return base


def _search_via_mcp(topic: str, depth: str, limit: int, api_base: str) -> List[Dict[str, Any]]:
    """通过 xiaohongshu-mcp HTTP API 搜索（POST /api/v1/feeds/search）。"""
    base = api_base.rstrip("/")
    try:
        login = http.get(f"{base}/api/v1/login/status", timeout=6, retries=1)
        logged_in = isinstance(login, dict) and (login.get("data") or {}).get("is_logged_in")
        if not logged_in:
            sys.stderr.write("[小红书] xiaohongshu-mcp 可访问但未登录，请先在 MCP 中完成扫码登录。\n")
            return []
    except Exception as e:
        sys.stderr.write(f"[小红书] xiaohongshu-mcp 不可用（{base}）: {e}\n")
        return []

    publish_time = {"quick": "一周内", "default": "半年内", "deep": "半年内"}.get(depth, "半年内")
    payload = {
        "keyword": topic,
        "filters": {
            "sort_by": "综合",
            "note_type": "不限",
            "publish_time": publish_time,
            "search_scope": "不限",
            "location": "不限",
        },
    }
    feeds: List[Any] = []
    try:
        resp = http.post(f"{base}/api/v1/feeds/search", payload, timeout=40, retries=1)
        feeds = ((resp or {}).get("data") or {}).get("feeds") or []
    except http.HTTPError as e:
        if e.status_code in (404, 405):
            feeds = _search_via_mcp_legacy(topic, limit, base)
        else:
            sys.stderr.write(f"[小红书] MCP 搜索失败: {e}\n")
    except Exception as e:
        sys.stderr.write(f"[小红书] MCP 搜索失败: {e}\n")

    items = [parsed for parsed in (parse_mcp_feed(feed) for feed in feeds[:limit]) if parsed]
    if items:
        sys.stderr.write(f"[小红书] xiaohongshu-mcp 返回 {len(items)} 条笔记\n")
    return items


def _search_via_mcp_legacy(topic: str, limit: int, base: str) -> List[Any]:
    """Older community servers exposed GET /api/v1/search/notes."""
    try:
        resp = http.get(
            f"{base}/api/v1/search/notes?keyword={urllib.parse.quote(topic)}&limit={limit}",
            timeout=30,
            retries=1,
        )
        data = (resp or {}).get("data")
        if isinstance(data, dict):
            return data.get("items") or data.get("feeds") or []
        if isinstance(data, list):
            return data
    except Exception as e:
        sys.stderr.write(f"[小红书] MCP 旧版接口失败: {e}\n")
    return []


def parse_mcp_feed(feed: Any) -> Optional[Dict[str, Any]]:
    """Normalize one xiaohongshu-mcp feed (camelCase) or legacy note (snake_case)."""
    if not isinstance(feed, dict):
        return None
    note = feed.get("noteCard") or feed.get("note_card") or feed
    if not isinstance(note, dict):
        return None
    interact = note.get("interactInfo") or note.get("interact_info") or {}
    user = note.get("user") or {}
    note_id = str(feed.get("id") or note.get("noteId") or note.get("note_id") or "").strip()
    if not note_id:
        return None
    xsec = feed.get("xsecToken") or note.get("xsecToken") or feed.get("xsec_token") or ""
    title = note.get("displayTitle") or note.get("display_title") or note.get("title") or ""
    desc = note.get("desc") or note.get("displayDesc") or ""
    ts = note.get("time") or note.get("lastUpdateTime")
    date_str = None
    if ts:
        try:
            value = int(ts)
            date_str = dates.timestamp_to_date(value / 1000 if value > 10_000_000_000 else value)
        except (TypeError, ValueError):
            date_str = None
    return {
        "title": str(title).strip(),
        "desc": str(desc).strip(),
        "url": note_url(note_id, xsec),
        "author_name": user.get("nickname") or user.get("nickName") or user.get("name") or "",
        "author_id": user.get("userId") or user.get("user_id") or "",
        "date": date_str,
        "engagement": {
            "likes": parse_count(interact.get("likedCount", interact.get("liked_count"))),
            "collects": parse_count(interact.get("collectedCount", interact.get("collected_count"))),
            "comments": parse_count(interact.get("commentCount", interact.get("comment_count"))),
            "shares": parse_count(interact.get("sharedCount", interact.get("share_count"))),
        },
        "hashtags": re.findall(r"#([^#\s]+)#?", f"{title} {desc}")[:10],
        "source": "xiaohongshu-mcp",
    }


def _search_via_site_search(topic: str, limit: int) -> List[Dict[str, Any]]:
    """Fallback to public web search when Xiaohongshu blocks MCP/Playwright."""
    items: List[Dict[str, Any]] = []
    for result in websearch.site_search(
        "xiaohongshu.com", topic, limit=limit, url_pattern=NOTE_URL_PATTERN, label="小红书"
    ):
        title = re.sub(r"\s*-\s*小红书\s*$", "", result.title).strip()
        if title in ("小红书", "你的生活兴趣社区 - 小红书", ""):
            title = result.snippet[:60] or result.title
        items.append({
            "title": title,
            "desc": result.snippet,
            "url": result.url,
            "author_name": "",
            "author_id": "",
            "date": result.date,
            "engagement": None,
            "hashtags": re.findall(r"#([^#\s]+)#?", f"{title} {result.snippet}")[:10],
            "images": [],
            "source": f"site-search:{result.engine}",
        })
    if items:
        sys.stderr.write(f"[小红书] 平台内路径无结果，已用公开搜索兜底获取 {len(items)} 条笔记链接。\n")
    return items


def parse_count(value: Any) -> int:
    """Parse counts like 1200 / '1.2万' / '3亿' / '10+'."""
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip().lower().replace(",", "").rstrip("+")
    if not text:
        return 0
    try:
        if text.endswith("万") or text.endswith("w"):
            return int(float(text[:-1]) * 10000)
        if text.endswith("亿"):
            return int(float(text[:-1]) * 100000000)
        if text.endswith("k"):
            return int(float(text[:-1]) * 1000)
        return int(float(text))
    except ValueError:
        return 0


def _parse_note(note: dict) -> Dict[str, Any]:
    """兼容旧调用：解析 snake_case 笔记数据。"""
    parsed = parse_mcp_feed(note) or {}
    if not parsed:
        note_id = note.get("note_id") or note.get("id", "")
        parsed = {
            "title": note.get("title") or note.get("display_title", ""),
            "desc": note.get("desc") or "",
            "url": note_url(str(note_id)) if note_id else "",
            "author_name": "",
            "author_id": "",
            "date": None,
            "engagement": {"likes": 0, "collects": 0, "comments": 0, "shares": 0},
            "hashtags": [],
        }
    return parsed
