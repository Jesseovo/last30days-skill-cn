"""Reddit 源（opt-in 海外源，issue #9）。

Author: Jesse (https://github.com/Jesseovo)

使用 Reddit 公开 JSON 搜索（免 Key）。注意：Reddit 经常对云服务器 / 代理 / 数据中心
IP 直接返回 403，这种情况下会明确报错，并建议改用上游引擎桥接（``--search upstream``）。
"""

import urllib.parse
from datetime import datetime
from typing import Any, Dict, List

from . import dates, http, relevance

HOSTS = ("https://www.reddit.com", "https://old.reddit.com")


def _time_filter(from_date: str, to_date: str) -> str:
    try:
        span = (datetime.strptime(to_date, "%Y-%m-%d") - datetime.strptime(from_date, "%Y-%m-%d")).days
    except (TypeError, ValueError):
        return "month"
    if span <= 1:
        return "day"
    if span <= 7:
        return "week"
    if span <= 31:
        return "month"
    return "year"


def search_reddit(query: str, from_date: str, to_date: str, depth: str = "default") -> List[Dict[str, Any]]:
    limit = {"quick": 10, "default": 25, "deep": 50}.get(depth, 25)
    params = {
        "q": query,
        "sort": "relevance",
        "t": _time_filter(from_date, to_date),
        "limit": str(limit),
        "raw_json": "1",
        "type": "link",
    }
    headers = {"User-Agent": http.USER_AGENT, "Accept": "application/json"}
    last_error = None
    data = None
    for host in HOSTS:
        try:
            data = http.get(f"{host}/search.json?{urllib.parse.urlencode(params)}", headers=headers, timeout=15, retries=1)
            break
        except http.HTTPError as exc:
            last_error = exc
            if exc.status_code not in (403, 429):
                break
    if data is None:
        if last_error is not None and last_error.status_code in (403, 429):
            raise http.HTTPError(
                f"Reddit 拒绝了当前网络的匿名请求（HTTP {last_error.status_code}），常见于云服务器/代理 IP；"
                "可换家庭网络重试，或安装上游 last30days 后使用 --search upstream",
                last_error.status_code,
            )
        raise last_error or http.HTTPError("Reddit 搜索失败")

    items = []
    for child in ((data or {}).get("data") or {}).get("children") or []:
        parsed = parse_post((child or {}).get("data") or {})
        if parsed and (not parsed["date"] or from_date <= parsed["date"] <= to_date):
            items.append(parsed)
    for item in items:
        item["relevance"] = relevance.token_overlap_relevance(query, f"{item['title']} {item.get('text', '')}")
    items.sort(key=lambda x: x.get("relevance", 0), reverse=True)
    for i, item in enumerate(items):
        item["id"] = f"RD{i+1}"
    return items


def parse_post(post: Dict[str, Any]) -> Dict[str, Any]:
    permalink = post.get("permalink") or ""
    title = post.get("title") or ""
    if not permalink or not title:
        return {}
    created = post.get("created_utc")
    sub = post.get("subreddit_name_prefixed") or ""
    return {
        "platform": "reddit",
        "title": title,
        "url": f"https://www.reddit.com{permalink}",
        "text": (post.get("selftext") or "")[:300],
        "author": post.get("author") or "",
        "container": sub,
        "date": dates.timestamp_to_date(created) if created else None,
        "engagement": {"score": post.get("score") or 0, "comments": post.get("num_comments") or 0},
        "why_relevant": f"Reddit {sub}：{post.get('score', 0)} upvotes / {post.get('num_comments', 0)} 评论",
        "source": "reddit-json",
    }
