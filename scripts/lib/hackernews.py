"""Hacker News 源（opt-in 海外源，issue #9）。

Author: Jesse (https://github.com/Jesseovo)

使用公开的 Algolia HN Search API（免 Key）：在研究时间窗内按相关性检索 story，
返回讨论链接、points 与评论数。中文主题需要英文关键词（``--global-query``）。
"""

import urllib.parse
from datetime import datetime
from typing import Any, Dict, List

from . import dates, http, relevance

SEARCH_URL = "https://hn.algolia.com/api/v1/search"
FRONT_PAGE_URL = "https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage={limit}"


def _window(from_date: str, to_date: str):
    start = datetime.strptime(from_date, "%Y-%m-%d").replace(tzinfo=dates.CST)
    end = datetime.strptime(to_date, "%Y-%m-%d").replace(tzinfo=dates.CST)
    return int(start.timestamp()), int(end.timestamp()) + 86399


def search_hackernews(query: str, from_date: str, to_date: str, depth: str = "default") -> List[Dict[str, Any]]:
    """Search HN stories in the window. Raises HTTPError on API failure."""
    limit = {"quick": 10, "default": 20, "deep": 40}.get(depth, 20)
    start, end = _window(from_date, to_date)
    params = {
        "query": query,
        "tags": "story",
        "numericFilters": f"created_at_i>{start},created_at_i<{end}",
        "hitsPerPage": str(limit),
    }
    data = http.get(f"{SEARCH_URL}?{urllib.parse.urlencode(params)}", timeout=15, retries=2)
    items = [parse_hit(hit) for hit in (data or {}).get("hits") or []]
    items = [item for item in items if item]
    for item in items:
        item["relevance"] = relevance.token_overlap_relevance(query, f"{item['title']} {item.get('text', '')}")
        item["why_relevant"] = (
            f"Hacker News：{item['engagement'].get('score', 0)} points / "
            f"{item['engagement'].get('comments', 0)} 评论"
        )
    items.sort(key=lambda x: x.get("relevance", 0), reverse=True)
    for i, item in enumerate(items[:limit]):
        item["id"] = f"HN{i+1}"
    return items[:limit]


def parse_hit(hit: Dict[str, Any]) -> Dict[str, Any]:
    object_id = hit.get("objectID") or ""
    title = hit.get("title") or hit.get("story_title") or ""
    if not object_id or not title:
        return {}
    story_url = hit.get("url") or ""
    created = hit.get("created_at_i")
    text = (hit.get("story_text") or "")[:300]
    if story_url:
        text = f"{story_url} {text}".strip()
    return {
        "platform": "hackernews",
        "title": title,
        "url": f"https://news.ycombinator.com/item?id={object_id}",
        "text": text,
        "author": hit.get("author") or "",
        "container": urllib.parse.urlsplit(story_url).netloc if story_url else "Ask/Show HN",
        "date": dates.timestamp_to_date(created) if created else None,
        "engagement": {"score": hit.get("points") or 0, "comments": hit.get("num_comments") or 0},
        "source": "algolia",
    }


def fetch_front_page(limit: int = 30) -> List[Dict[str, Any]]:
    """HN front page (used by the trending board's overseas section)."""
    data = http.get(FRONT_PAGE_URL.format(limit=limit), timeout=12, retries=1)
    out = []
    for rank, hit in enumerate((data or {}).get("hits") or [], start=1):
        parsed = parse_hit(hit)
        if not parsed:
            continue
        out.append({
            "rank": rank,
            "title": parsed["title"],
            "url": parsed["url"],
            "hot_value": parsed["engagement"]["score"],
            "label": f"{parsed['engagement']['comments']} 评论" if parsed["engagement"]["comments"] else "",
        })
    out.sort(key=lambda x: x.get("hot_value") or 0, reverse=True)
    for rank, item in enumerate(out, start=1):
        item["rank"] = rank
    return out
