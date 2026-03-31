"""B站搜索模块 - 搜索哔哩哔哩视频内容。

Author: Jesse (https://github.com/ChiTing111)

使用 B站公开搜索 API（无需 API Key）。
"""

import json
import re
import sys
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from . import relevance

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def search_bilibili(
    topic: str,
    from_date: str,
    to_date: str,
    depth: str = "default",
) -> List[Dict[str, Any]]:
    """搜索B站视频。

    Args:
        topic: 搜索关键词
        from_date: 起始日期 YYYY-MM-DD
        to_date: 结束日期 YYYY-MM-DD
        depth: 搜索深度 quick/default/deep

    Returns:
        B站视频列表
    """
    limit_map = {"quick": 10, "default": 20, "deep": 40}
    limit = limit_map.get(depth, 20)
    pages = 1 if depth == "quick" else (2 if depth == "default" else 3)

    items: List[Dict[str, Any]] = []

    for page in range(1, pages + 1):
        try:
            page_items = _search_page(topic, page)
            items.extend(page_items)
        except Exception as e:
            sys.stderr.write(f"[B站] 搜索第 {page} 页失败: {e}\n")
            break

    scored = []
    for i, item in enumerate(items):
        title = _clean_html(item.get("title", ""))
        rel = relevance.token_overlap_relevance(topic, title)
        item["id"] = f"BL{i+1}"
        item["title"] = title
        item["relevance"] = rel
        item["why_relevant"] = f"B站视频：{title[:50]}"
        scored.append(item)

    scored.sort(key=lambda x: x.get("relevance", 0), reverse=True)
    return scored[:limit]


def _search_page(topic: str, page: int = 1) -> List[Dict[str, Any]]:
    """搜索B站单页结果。"""
    encoded = urllib.parse.quote(topic)
    url = (
        f"https://api.bilibili.com/x/web-interface/search/type"
        f"?search_type=video&keyword={encoded}&page={page}&page_size=20"
        f"&order=totalrank"
    )
    headers = {
        "User-Agent": _UA,
        "Referer": "https://search.bilibili.com/",
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as response:
        data = json.loads(response.read().decode("utf-8"))

    items = []
    results = data.get("data", {}).get("result", [])
    if not results:
        return items

    for r in results:
        items.append(_parse_video(r))

    return items


def _parse_video(v: dict) -> Dict[str, Any]:
    """解析B站视频搜索结果。"""
    bvid = v.get("bvid", "")
    pubdate = v.get("pubdate", 0)
    date_str = None
    if pubdate:
        try:
            from datetime import datetime
            date_str = datetime.fromtimestamp(pubdate).strftime("%Y-%m-%d")
        except Exception:
            pass

    return {
        "title": v.get("title", ""),
        "url": f"https://www.bilibili.com/video/{bvid}" if bvid else v.get("arcurl", ""),
        "bvid": bvid,
        "channel_name": v.get("author", ""),
        "author_mid": v.get("mid", ""),
        "date": date_str,
        "duration": v.get("duration", ""),
        "description": v.get("description", ""),
        "engagement": {
            "views": v.get("play", 0),
            "danmaku": v.get("danmaku", 0),
            "comments": v.get("review", 0) or v.get("comment", 0),
            "favorites": v.get("favorites", 0),
            "likes": v.get("like", 0),
        },
    }


def _clean_html(text: str) -> str:
    """清除搜索结果中的 HTML 高亮标签。"""
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()
