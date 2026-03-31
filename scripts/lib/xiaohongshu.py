"""小红书搜索模块 - 搜索小红书笔记。

Author: Jesse (https://github.com/ChiTing111)

支持多种数据获取方式：
1. ScrapeCreators API（推荐，同一个 key 也支持抖音）
2. 公开搜索接口
"""

import json
import re
import sys
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from . import http, relevance

_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15"


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
        token: ScrapeCreators API key（可选）
        api_base: 自定义 API 地址（可选）

    Returns:
        小红书笔记列表
    """
    limit_map = {"quick": 10, "default": 20, "deep": 40}
    limit = limit_map.get(depth, 20)

    items: List[Dict[str, Any]] = []

    if api_base:
        items = _search_via_mcp(topic, from_date, to_date, limit, api_base)

    if not items and token:
        items = _search_via_scrapecreators(topic, from_date, to_date, limit, token)

    if not items:
        items = _search_via_public(topic, limit)

    scored = []
    for i, item in enumerate(items):
        title = item.get("title", "")
        desc = item.get("desc", "")
        combined = f"{title} {desc}"
        rel = relevance.token_overlap_relevance(topic, combined)
        item["id"] = f"XHS{i+1}"
        item["relevance"] = rel
        item["why_relevant"] = f"小红书笔记：{title[:50]}"
        scored.append(item)

    scored.sort(key=lambda x: x.get("relevance", 0), reverse=True)
    return scored[:limit]


def _search_via_mcp(
    topic: str, from_date: str, to_date: str, limit: int, api_base: str
) -> List[Dict[str, Any]]:
    """通过 xiaohongshu-mcp HTTP API 搜索。"""
    items = []
    try:
        base = api_base.rstrip("/")
        encoded = urllib.parse.quote(topic)
        url = f"{base}/api/v1/search/notes?keyword={encoded}&limit={limit}"
        resp = http.get(url, timeout=15)
        if isinstance(resp, dict) and resp.get("data"):
            for note in resp["data"].get("items", resp["data"] if isinstance(resp["data"], list) else []):
                items.append(_parse_note(note))
    except Exception as e:
        sys.stderr.write(f"[小红书] MCP API 搜索失败: {e}\n")
    return items


def _search_via_scrapecreators(
    topic: str, from_date: str, to_date: str, limit: int, token: str
) -> List[Dict[str, Any]]:
    """通过 ScrapeCreators API 搜索小红书。"""
    items = []
    try:
        encoded = urllib.parse.quote(topic)
        url = f"https://api.scrapecreators.com/v2/xiaohongshu/search?keyword={encoded}&limit={limit}"
        resp = http.get(url, timeout=15, headers={"x-api-key": token})
        if isinstance(resp, dict):
            for note in resp.get("data", []):
                items.append(_parse_note(note))
    except Exception as e:
        sys.stderr.write(f"[小红书] ScrapeCreators 搜索失败: {e}\n")
    return items


def _search_via_public(topic: str, limit: int) -> List[Dict[str, Any]]:
    """通过公开接口搜索小红书（备用方案）。"""
    items = []
    try:
        encoded = urllib.parse.quote(topic)
        url = f"https://www.xiaohongshu.com/fe_api/burdock/weixin/v2/search/notes?keyword={encoded}&page=1&page_size={limit}"
        headers = {"User-Agent": _UA}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
        for note in data.get("data", {}).get("notes", []):
            items.append(_parse_note(note))
    except Exception as e:
        sys.stderr.write(f"[小红书] 公开接口搜索失败: {e}\n")
    return items


def _parse_note(note: dict) -> Dict[str, Any]:
    """解析小红书笔记数据。"""
    note_id = note.get("note_id") or note.get("id", "")
    title = note.get("title") or note.get("display_title", "")
    desc = note.get("desc") or note.get("description", "")
    user = note.get("user", {}) if isinstance(note.get("user"), dict) else {}
    liked_count = note.get("liked_count") or note.get("likes", 0)
    collected_count = note.get("collected_count") or note.get("collects", 0)
    comment_count = note.get("comment_count") or note.get("comments", 0)
    share_count = note.get("share_count") or note.get("shares", 0)

    # 提取话题标签
    hashtags = re.findall(r"#([^#\s]+)#?", f"{title} {desc}")

    date_str = note.get("time") or note.get("created_time") or note.get("date")
    if date_str and len(str(date_str)) == 13:
        try:
            from datetime import datetime
            date_str = datetime.fromtimestamp(int(date_str) / 1000).strftime("%Y-%m-%d")
        except Exception:
            date_str = None
    elif date_str and len(str(date_str)) == 10 and str(date_str).isdigit():
        try:
            from datetime import datetime
            date_str = datetime.fromtimestamp(int(date_str)).strftime("%Y-%m-%d")
        except Exception:
            date_str = None

    return {
        "title": title,
        "desc": desc,
        "url": f"https://www.xiaohongshu.com/explore/{note_id}" if note_id else "",
        "author_name": user.get("nickname") or user.get("name", ""),
        "author_id": user.get("user_id") or user.get("id", ""),
        "date": date_str,
        "engagement": {
            "likes": _safe_int(liked_count),
            "collects": _safe_int(collected_count),
            "comments": _safe_int(comment_count),
            "shares": _safe_int(share_count),
        },
        "hashtags": hashtags,
        "images": note.get("images_list") or note.get("image_list", []),
    }


def _safe_int(val) -> int:
    """安全转换为整数。"""
    if val is None:
        return 0
    try:
        return int(val)
    except (ValueError, TypeError):
        return 0
