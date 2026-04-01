"""今日头条搜索模块 - 提供热点趋势和资讯搜索。

Author: Jesse (https://github.com/ChiTing111)

使用今日头条搜索 API 和热榜接口。
"""

import json
import re
import sys
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from . import relevance

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def search_toutiao(
    topic: str,
    from_date: str,
    to_date: str,
    depth: str = "default",
) -> List[Dict[str, Any]]:
    """搜索今日头条内容。

    Args:
        topic: 搜索关键词
        from_date: 起始日期
        to_date: 结束日期
        depth: 搜索深度

    Returns:
        头条文章/视频列表
    """
    limit_map = {"quick": 10, "default": 20, "deep": 30}
    limit = limit_map.get(depth, 20)

    items: List[Dict[str, Any]] = []

    search_items = _search_content(topic, limit)
    items.extend(search_items)

    if depth != "quick":
        hot_items = _get_hot_related(topic)
        existing_titles = {it.get("title", "").lower() for it in items}
        for hi in hot_items:
            if hi.get("title", "").lower() not in existing_titles:
                items.append(hi)

    scored = []
    for i, item in enumerate(items):
        title = item.get("title", "")
        abstract = item.get("abstract", "")
        combined = f"{title} {abstract}"
        rel = relevance.token_overlap_relevance(topic, combined)
        item["id"] = f"TT{i+1}"
        item["relevance"] = rel
        item["why_relevant"] = f"今日头条：{title[:50]}"
        scored.append(item)

    scored.sort(key=lambda x: x.get("relevance", 0), reverse=True)
    return scored[:limit]


def _search_content(topic: str, limit: int) -> List[Dict[str, Any]]:
    """搜索头条内容。"""
    items = []
    try:
        encoded = urllib.parse.quote(topic)
        url = f"https://www.toutiao.com/api/search/content/?keyword={encoded}&count={min(limit, 20)}&offset=0"
        headers = {
            "User-Agent": _UA,
            "Referer": "https://www.toutiao.com/",
            "Cookie": "tt_webid=1",
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))

        for entry in data.get("data", []):
            parsed = _parse_article(entry)
            if parsed:
                items.append(parsed)
    except Exception as e:
        sys.stderr.write(f"[今日头条] 内容搜索失败: {e}\n")
    return items


def _get_hot_related(topic: str) -> List[Dict[str, Any]]:
    """从头条热榜中查找相关话题。"""
    items = []
    try:
        url = "https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc"
        headers = {"User-Agent": _UA}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))

        topic_lower = topic.lower()
        for entry in data.get("data", []):
            title = entry.get("Title", "")
            if any(kw in title.lower() for kw in topic_lower.split()):
                items.append({
                    "title": title,
                    "abstract": entry.get("Abstract", ""),
                    "url": entry.get("Url", ""),
                    "source_name": "今日头条热榜",
                    "date": None,
                    "is_hot": True,
                    "hot_value": entry.get("HotValue", 0),
                    "engagement": {
                        "hot_value": entry.get("HotValue", 0),
                    },
                })
    except Exception as e:
        sys.stderr.write(f"[今日头条] 热榜搜索失败: {e}\n")
    return items


def _parse_article(entry: dict) -> Optional[Dict[str, Any]]:
    """解析头条文章。"""
    title = entry.get("title", "")
    if not title:
        return None

    date_str = None
    publish_time = entry.get("publish_time") or entry.get("behot_time", 0)
    if publish_time:
        try:
            from datetime import datetime
            date_str = datetime.fromtimestamp(int(publish_time)).strftime("%Y-%m-%d")
        except Exception:
            pass

    article_url = entry.get("article_url") or entry.get("display_url", "")
    if article_url and not article_url.startswith("http"):
        article_url = f"https://www.toutiao.com{article_url}"

    return {
        "title": _clean_html(title),
        "abstract": _clean_html(entry.get("abstract", "")),
        "url": article_url,
        "source_name": entry.get("source", "") or entry.get("media_name", ""),
        "date": date_str,
        "engagement": {
            "comments": entry.get("comment_count", 0),
            "likes": entry.get("digg_count", 0) or entry.get("like_count", 0),
            "reads": entry.get("read_count", 0),
        },
    }


def _clean_html(text: str) -> str:
    """清除 HTML 标签。"""
    return re.sub(r"<[^>]+>", "", text).strip()
