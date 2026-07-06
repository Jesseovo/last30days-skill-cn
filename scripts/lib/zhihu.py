"""知乎搜索模块 - 搜索知乎问答和文章。

Author: Jesse (https://github.com/Jesseovo)

支持两种模式（自动切换）：
1. 知乎公开搜索接口和热榜 API
2. MediaCrawler 浏览器爬虫（备用方案）
"""

import json
import re
import sys
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from . import dates, relevance

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


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

    search_items = _search_general(topic, limit, cookie)
    items.extend(search_items)

    if not items and depth != "quick":
        try:
            from . import crawler_bridge
            if crawler_bridge.is_playwright_available():
                sys.stderr.write("[知乎] API 无结果，尝试 MediaCrawler 爬虫模式...\n")
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
        items = _search_via_site_search(topic, limit)

    scored = []
    for i, item in enumerate(items):
        title = item.get("title", "")
        excerpt = item.get("excerpt", "")
        combined = f"{title} {excerpt}"
        rel = relevance.token_overlap_relevance(topic, combined)
        item["id"] = f"ZH{i+1}"
        item["relevance"] = rel
        source = item.get("source", "zhihu")
        item["why_relevant"] = f"知乎来源({source}): {title[:50]}"
        scored.append(item)

    scored.sort(key=lambda x: x.get("relevance", 0), reverse=True)
    return scored[:limit]


def _search_general(
    topic: str, limit: int, cookie: Optional[str] = None
) -> List[Dict[str, Any]]:
    """通过知乎搜索 API 搜索。"""
    items = []
    try:
        encoded = urllib.parse.quote(topic)
        url = f"https://www.zhihu.com/api/v4/search_v3?t=general&q={encoded}&offset=0&limit={min(limit, 20)}"
        headers = {
            "User-Agent": _UA,
            "Referer": "https://www.zhihu.com/",
        }
        if cookie:
            headers["Cookie"] = cookie

        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as response:
            data = json.loads(response.read().decode("utf-8"))

        for entry in data.get("data", []):
            obj = entry.get("object", {})
            item_type = entry.get("type", "")

            if item_type in ("search_result",):
                obj = entry.get("object", entry)

            parsed = _parse_search_result(obj, item_type)
            if parsed:
                items.append(parsed)
    except Exception as e:
        sys.stderr.write(f"[知乎] 搜索失败: {e}\n")
    return items


def _search_hot_related(topic: str) -> List[Dict[str, Any]]:
    """从知乎热榜中查找相关话题。"""
    items = []
    try:
        url = "https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total?limit=50"
        headers = {"User-Agent": _UA}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as response:
            data = json.loads(response.read().decode("utf-8"))

        topic_lower = topic.lower()
        for entry in data.get("data", []):
            target = entry.get("target", {})
            title = target.get("title", "")
            if any(kw in title.lower() for kw in topic_lower.split()):
                items.append({
                    "title": title,
                    "url": f"https://www.zhihu.com/question/{target.get('id', '')}",
                    "excerpt": target.get("excerpt", ""),
                    "author": target.get("author", {}).get("name", ""),
                    "date": None,
                    "content_type": "hot_question",
                    "engagement": {
                        "voteups": target.get("follower_count", 0),
                        "comments": target.get("answer_count", 0),
                    },
                })
    except Exception as e:
        sys.stderr.write(f"[知乎] 热榜搜索失败: {e}\n")
    return items


def _fetch_html(url: str, timeout: int = 8) -> str:
    headers = {
        "User-Agent": _UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "identity",
        "Referer": "https://cn.bing.com/",
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def _search_via_site_search(topic: str, limit: int) -> List[Dict[str, Any]]:
    """Fallback to public web search when Zhihu API/Playwright paths return empty."""
    items: List[Dict[str, Any]] = []
    try:
        query = f"site:zhihu.com/question OR site:zhuanlan.zhihu.com/p {topic}"
        encoded = urllib.parse.quote(query)
        url = f"https://cn.bing.com/search?q={encoded}&setmkt=zh-CN&ensearch=0"
        html = _fetch_html(url)
        blocks = re.findall(r'<li class="b_algo"[^>]*>([\s\S]*?)</li>', html)
        seen = set()
        for block in blocks:
            title_match = re.search(
                r'<h2[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>\s*</h2>',
                block,
                re.S,
            )
            if not title_match:
                continue
            href = title_match.group(1)
            if ("zhihu.com" not in href and "zhuanlan.zhihu.com" not in href) or href in seen:
                continue
            seen.add(href)
            title = _clean_html(title_match.group(2))
            snip_match = re.search(r"<p[^>]*>([\s\S]*?)</p>", block, re.S)
            snippet = _clean_html(snip_match.group(1)) if snip_match else ""
            content_type = "article" if "zhuanlan.zhihu.com" in href else "question"
            items.append({
                "title": title,
                "excerpt": snippet,
                "url": href,
                "author": "",
                "date": None,
                "content_type": content_type,
                "engagement": {"voteups": 0, "comments": 0, "collects": 0},
                "source": "site-search-fallback",
            })
            if len(items) >= limit:
                break
    except Exception as e:
        sys.stderr.write(f"[知乎] 站内搜索兜底失败: {e}\n")
    if items:
        sys.stderr.write(f"[知乎] API/Playwright 路径无结果，已用站内搜索兜底获取 {len(items)} 条公开链接。\n")
    return items


def _parse_search_result(obj: dict, item_type: str = "") -> Optional[Dict[str, Any]]:
    """解析知乎搜索结果条目。"""
    if not obj:
        return None

    title = _clean_html(obj.get("title") or obj.get("name", ""))
    if not title:
        title = _clean_html(obj.get("question", {}).get("title", "")) if isinstance(obj.get("question"), dict) else ""
    if not title:
        return None

    excerpt = _clean_html(obj.get("excerpt") or obj.get("content", ""))[:300]
    author = ""
    author_obj = obj.get("author", {})
    if isinstance(author_obj, dict):
        author = author_obj.get("name", "")

    obj_type = obj.get("type", item_type)
    url = ""
    if obj_type == "answer":
        qid = obj.get("question", {}).get("id", "") if isinstance(obj.get("question"), dict) else ""
        aid = obj.get("id", "")
        url = f"https://www.zhihu.com/question/{qid}/answer/{aid}" if qid else ""
    elif obj_type == "article":
        url = f"https://zhuanlan.zhihu.com/p/{obj.get('id', '')}"
    elif obj_type == "question":
        url = f"https://www.zhihu.com/question/{obj.get('id', '')}"
    else:
        url = obj.get("url", "")

    created = obj.get("created_time") or obj.get("created", 0)
    date_str = None
    if created and isinstance(created, (int, float)) and created > 1000000000:
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
    }


def _clean_html(text: str) -> str:
    """清除 HTML 标签。"""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", str(text))
    return text.strip()
