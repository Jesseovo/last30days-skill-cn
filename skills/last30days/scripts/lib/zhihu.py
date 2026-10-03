"""知乎搜索模块 - 搜索知乎问答和文章。

Author: Jesse (https://github.com/Jesseovo)

v4 数据路径：
1. ``search_v3`` 接口 + ``ZHIHU_COOKIE``（匿名请求现在恒返回 400/403，
   v4 起只在配置 Cookie 时调用，避免触发风控）。
2. Playwright 浏览器（复用 ``login zhihu`` 登录态，拦截页面自己发出的
   ``search_v3`` XHR，比 DOM 解析稳定）。
3. 知乎热榜中与主题相关的问题（接口可用时）。
4. ``site:zhihu.com`` 公开搜索兜底（只接受问题/回答/专栏链接，带相关性校验）。
"""

import re
import sys
import urllib.parse
from typing import Any, Dict, List, Optional

from . import dates, http, relevance, websearch

SEARCH_URL = "https://www.zhihu.com/api/v4/search_v3"
HOT_LIST_URLS = (
    "https://api.zhihu.com/topstory/hot-lists/total?limit=50",
    "https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total?limit=50",
)
CONTENT_URL_PATTERN = r"(?:zhihu\.com/question/\d+|zhuanlan\.zhihu\.com/p/\d+)"
LOGIN_HINT = (
    "知乎搜索需要登录：配置 ZHIHU_COOKIE，或运行 "
    "`python scripts/last30days.py login zhihu`（需 Playwright）保存登录态"
)


def search_zhihu(
    topic: str,
    from_date: str,
    to_date: str,
    depth: str = "default",
    cookie: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """搜索知乎内容。

    Args:
        topic: 搜索关键词
        from_date: 起始日期 YYYY-MM-DD
        to_date: 结束日期 YYYY-MM-DD
        depth: 搜索深度 quick/default/deep
        cookie: 知乎 Cookie（可选，提升搜索质量）

    Returns:
        知乎问答/文章列表
    """
    limit_map = {"quick": 10, "default": 20, "deep": 40}
    limit = limit_map.get(depth, 20)

    items: List[Dict[str, Any]] = []
    attempted: List[str] = []

    if cookie:
        attempted.append("search_v3+Cookie")
        items.extend(_search_general(topic, limit, cookie))

    if not items and depth != "quick":
        try:
            from . import crawler_bridge
            if crawler_bridge.is_playwright_available():
                attempted.append("Playwright")
                sys.stderr.write("[知乎] 尝试浏览器爬虫模式...\n")
                items = crawler_bridge.crawl_zhihu(topic, limit)
                if items:
                    sys.stderr.write(f"[知乎] 爬虫模式获取 {len(items)} 条结果\n")
        except Exception as e:
            sys.stderr.write(f"[知乎] 爬虫模式失败: {e}\n")

    if depth != "quick":
        hot_items = _search_hot_related(topic)
        existing_urls = {it.get("url", "") for it in items}
        for hi in hot_items:
            if hi.get("url", "") not in existing_urls:
                items.append(hi)

    if not items:
        attempted.append("公开搜索")
        items = _search_via_site_search(topic, limit)

    if not items:
        raise http.HTTPError(
            "未获取到知乎结果；已尝试：" + " / ".join(attempted or ["公开搜索"]) + "。"
            + LOGIN_HINT + "。" + websearch.describe_failure("知乎")
        )

    scored = []
    for item in items:
        title = item.get("title", "")
        excerpt = item.get("excerpt", "")
        rel = relevance.token_overlap_relevance(topic, f"{title} {excerpt}")
        item["relevance"] = rel
        source = item.get("source", "zhihu")
        item["why_relevant"] = f"知乎来源({source}): {title[:50]}"
        scored.append(item)

    scored.sort(key=lambda x: x.get("relevance", 0), reverse=True)
    scored = scored[:limit]
    for i, item in enumerate(scored):
        item["id"] = f"ZH{i+1}"
    return scored


def _search_general(topic: str, limit: int, cookie: Optional[str] = None) -> List[Dict[str, Any]]:
    """通过知乎搜索 API 搜索（需要登录 Cookie）。"""
    items = []
    try:
        params = {"t": "general", "q": topic, "offset": 0, "limit": min(limit, 20)}
        headers = http.browser_headers(referer="https://www.zhihu.com/search", accept="json")
        if cookie:
            headers["Cookie"] = cookie
        data = http.get(f"{SEARCH_URL}?{urllib.parse.urlencode(params)}", headers=headers, timeout=10, retries=1)
        items = parse_search_payload(data)
    except http.HTTPError as e:
        hint = "（Cookie 可能已过期或需要验证）" if e.status_code in (401, 403) else ""
        sys.stderr.write(f"[知乎] 搜索接口失败: {e}{hint}\n")
    except Exception as e:
        sys.stderr.write(f"[知乎] 搜索失败: {e}\n")
    return items


def parse_search_payload(data: Any) -> List[Dict[str, Any]]:
    """Parse a ``search_v3`` JSON payload (API or intercepted XHR)."""
    items = []
    for entry in ((data or {}).get("data") or []) if isinstance(data, dict) else []:
        if not isinstance(entry, dict):
            continue
        obj = entry.get("object") or {}
        item_type = entry.get("type", "")
        parsed = _parse_search_result(obj, item_type)
        if parsed:
            items.append(parsed)
    return items


def fetch_hot(limit: int = 50) -> List[Dict[str, Any]]:
    """知乎热榜（接口可能要求登录/风控，失败时抛出最后一个错误）。"""
    last_error: Optional[Exception] = None
    for url in HOT_LIST_URLS:
        try:
            data = http.get(url, headers=http.browser_headers(referer="https://www.zhihu.com/hot", accept="json"), timeout=8, retries=1)
        except Exception as exc:
            last_error = exc
            continue
        out = []
        for idx, entry in enumerate((data or {}).get("data") or [], start=1):
            target = entry.get("target") or {}
            title = target.get("title") or ""
            qid = target.get("id")
            if not title:
                continue
            detail = entry.get("detail_text") or ""
            heat = _parse_heat(detail)
            out.append({
                "rank": idx,
                "title": title,
                "url": f"https://www.zhihu.com/question/{qid}" if qid else "",
                "hot_value": heat,
                "label": "",
                "excerpt": target.get("excerpt", ""),
                "answer_count": target.get("answer_count", 0),
                "follower_count": target.get("follower_count", 0),
            })
            if len(out) >= limit:
                break
        if out:
            return out
    if last_error:
        raise last_error
    return []


def _parse_heat(detail: str) -> Optional[int]:
    """'1234 万热度' -> 12340000."""
    match = re.search(r"([\d.]+)\s*(万|亿)?\s*热度", detail or "")
    if not match:
        return None
    value = float(match.group(1))
    unit = match.group(2)
    if unit == "万":
        value *= 10000
    elif unit == "亿":
        value *= 100000000
    return int(value)


def _search_hot_related(topic: str) -> List[Dict[str, Any]]:
    """从知乎热榜中查找相关话题。"""
    try:
        hot = fetch_hot(50)
    except Exception as e:
        http.log(f"[知乎] 热榜获取失败: {e}")
        return []
    items = []
    for entry in hot:
        if relevance.token_overlap_relevance(topic, entry["title"]) < 0.35:
            continue
        items.append({
            "title": entry["title"],
            "url": entry["url"],
            "excerpt": entry.get("excerpt", ""),
            "author": "",
            "date": None,
            "content_type": "hot_question",
            "engagement": {
                "voteups": entry.get("follower_count", 0),
                "comments": entry.get("answer_count", 0),
            },
            "source": "hot-list",
        })
    return items


def _search_via_site_search(topic: str, limit: int) -> List[Dict[str, Any]]:
    """Fallback to public web search when Zhihu API/Playwright paths return empty."""
    items: List[Dict[str, Any]] = []
    for result in websearch.site_search(
        ["zhihu.com", "zhuanlan.zhihu.com"], topic, limit=limit,
        url_pattern=CONTENT_URL_PATTERN, label="知乎",
    ):
        title = re.sub(r"\s*-\s*知乎\s*$", "", result.title).strip()
        content_type = "article" if "zhuanlan.zhihu.com" in result.url else (
            "answer" if "/answer/" in result.url else "question"
        )
        items.append({
            "title": title,
            "excerpt": result.snippet,
            "url": result.url,
            "author": "",
            "date": result.date,
            "content_type": content_type,
            "engagement": None,
            "source": f"site-search:{result.engine}",
        })
    if items:
        sys.stderr.write(f"[知乎] 平台内路径无结果，已用公开搜索兜底获取 {len(items)} 条公开链接。\n")
    return items


def _parse_search_result(obj: dict, item_type: str = "") -> Optional[Dict[str, Any]]:
    """解析知乎搜索结果条目。"""
    if not obj or not isinstance(obj, dict):
        return None

    title = _clean_html(obj.get("title") or obj.get("name", ""))
    question = obj.get("question") if isinstance(obj.get("question"), dict) else {}
    if not title:
        title = _clean_html(question.get("name") or question.get("title", ""))
    if not title:
        return None

    excerpt = _clean_html(obj.get("excerpt") or obj.get("content", ""))[:300]
    author_obj = obj.get("author", {})
    author = author_obj.get("name", "") if isinstance(author_obj, dict) else ""

    obj_type = obj.get("type", item_type)
    if obj_type == "answer":
        qid = question.get("id", "")
        aid = obj.get("id", "")
        url = f"https://www.zhihu.com/question/{qid}/answer/{aid}" if qid else ""
    elif obj_type == "article":
        url = f"https://zhuanlan.zhihu.com/p/{obj.get('id', '')}"
    elif obj_type == "question":
        url = f"https://www.zhihu.com/question/{obj.get('id', '')}"
    else:
        url = obj.get("url", "")
        if "api.zhihu.com/questions/" in url:
            url = url.replace("api.zhihu.com/questions/", "www.zhihu.com/question/")

    created = obj.get("created_time") or obj.get("updated_time") or obj.get("created", 0)
    date_str = None
    if isinstance(created, (int, float)) and created > 1000000000:
        date_str = dates.timestamp_to_date(created)

    return {
        "title": title,
        "excerpt": excerpt,
        "url": url,
        "author": author,
        "date": date_str,
        "content_type": obj_type,
        "engagement": {
            "voteups": obj.get("voteup_count", 0),
            "comments": obj.get("comment_count", 0),
            "collects": obj.get("collected_count") or obj.get("favlists_count", 0),
        },
        "source": "search_v3",
    }


def _clean_html(text: str) -> str:
    """清除 HTML 标签。"""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", str(text))
    return text.strip()
