"""微博搜索模块 - 搜索微博热门内容。

Author: Jesse (https://github.com/ChiTing111)

支持两种模式：
1. 微博开放平台 API（需要 WEIBO_ACCESS_TOKEN）
2. 微博移动端公共接口（免费，无需认证）
"""

import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from . import http, relevance

_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15"


def search_weibo(
    topic: str,
    from_date: str,
    to_date: str,
    depth: str = "default",
    token: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """搜索微博内容。

    Args:
        topic: 搜索关键词
        from_date: 起始日期 YYYY-MM-DD
        to_date: 结束日期 YYYY-MM-DD
        depth: 搜索深度 quick/default/deep
        token: 微博 access_token（可选）

    Returns:
        微博条目列表，每条包含 id, text, url, author_handle, date,
        engagement, relevance, why_relevant 等字段
    """
    limit_map = {"quick": 15, "default": 30, "deep": 50}
    limit = limit_map.get(depth, 30)

    items: List[Dict[str, Any]] = []

    if token:
        items = _search_via_api(topic, from_date, to_date, limit, token)
    
    if not items:
        items = _search_via_public(topic, from_date, to_date, limit)

    scored = []
    for i, item in enumerate(items):
        text = item.get("text", "")
        rel = relevance.token_overlap_relevance(topic, text)
        item["id"] = f"WB{i+1}"
        item["relevance"] = rel
        item["why_relevant"] = f"微博讨论：{text[:60]}..."
        scored.append(item)

    scored.sort(key=lambda x: x.get("relevance", 0), reverse=True)
    return scored[:limit]


def _search_via_api(
    topic: str, from_date: str, to_date: str, limit: int, token: str
) -> List[Dict[str, Any]]:
    """通过微博开放平台 API 搜索。"""
    items = []
    try:
        encoded = urllib.parse.quote(topic)
        url = (
            f"https://api.weibo.com/2/search/statuses.json"
            f"?access_token={token}&q={encoded}&count={min(limit, 50)}"
        )
        resp = http.get(url, timeout=15)
        if isinstance(resp, dict) and "statuses" in resp:
            for s in resp["statuses"]:
                items.append(_parse_status(s))
    except Exception as e:
        sys.stderr.write(f"[微博] API 搜索失败: {e}\n")
    return items


def _search_via_public(
    topic: str, from_date: str, to_date: str, limit: int
) -> List[Dict[str, Any]]:
    """通过微博移动端公共接口搜索（无需认证）。"""
    items = []
    try:
        encoded = urllib.parse.quote(topic)
        url = f"https://m.weibo.cn/api/container/getIndex?containerid=100103type%3D1%26q%3D{encoded}&page_type=searchall"
        headers = {"User-Agent": _UA, "Referer": "https://m.weibo.cn/"}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))

        cards = data.get("data", {}).get("cards", [])
        for card in cards:
            if card.get("card_type") == 9:
                mblog = card.get("mblog", {})
                if mblog:
                    items.append(_parse_mblog(mblog))
            elif card.get("card_type") == 11:
                for group in card.get("card_group", []):
                    mblog = group.get("mblog", {})
                    if mblog:
                        items.append(_parse_mblog(mblog))
    except Exception as e:
        sys.stderr.write(f"[微博] 公共接口搜索失败: {e}\n")
    return items


def _parse_status(s: dict) -> Dict[str, Any]:
    """解析微博开放平台 API 返回的状态。"""
    text = _clean_html(s.get("text", ""))
    user = s.get("user", {})
    created = s.get("created_at", "")
    date_str = _parse_weibo_date(created)

    return {
        "text": text,
        "url": f"https://weibo.com/{user.get('id', '')}/{s.get('mid', '')}",
        "author_handle": user.get("screen_name", ""),
        "author_id": str(user.get("id", "")),
        "date": date_str,
        "engagement": {
            "reposts": s.get("reposts_count", 0),
            "comments": s.get("comments_count", 0),
            "likes": s.get("attitudes_count", 0),
        },
    }


def _parse_mblog(mblog: dict) -> Dict[str, Any]:
    """解析微博移动端接口返回的 mblog。"""
    text = _clean_html(mblog.get("text", ""))
    user = mblog.get("user", {})
    created = mblog.get("created_at", "")
    date_str = _parse_weibo_date(created)
    mid = mblog.get("mid", "") or mblog.get("id", "")

    return {
        "text": text,
        "url": f"https://weibo.com/{user.get('id', '')}/{mid}",
        "author_handle": user.get("screen_name", ""),
        "author_id": str(user.get("id", "")),
        "date": date_str,
        "engagement": {
            "reposts": mblog.get("reposts_count", 0),
            "comments": mblog.get("comments_count", 0),
            "likes": mblog.get("attitudes_count", 0),
        },
    }


def _clean_html(text: str) -> str:
    """清除微博文本中的 HTML 标签。"""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _parse_weibo_date(date_str: str) -> Optional[str]:
    """将微博日期格式转换为 YYYY-MM-DD。"""
    if not date_str:
        return None
    try:
        # "Tue Jan 01 00:00:00 +0800 2026"
        dt = datetime.strptime(date_str, "%a %b %d %H:%M:%S %z %Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        pass
    # 相对时间: "x分钟前", "x小时前", "昨天 HH:MM"
    now = datetime.now()
    if "分钟前" in date_str:
        try:
            mins = int(re.search(r"(\d+)", date_str).group(1))
            return (now - timedelta(minutes=mins)).strftime("%Y-%m-%d")
        except Exception:
            pass
    if "小时前" in date_str:
        try:
            hours = int(re.search(r"(\d+)", date_str).group(1))
            return (now - timedelta(hours=hours)).strftime("%Y-%m-%d")
        except Exception:
            pass
    if "昨天" in date_str:
        return (now - timedelta(days=1)).strftime("%Y-%m-%d")
    # "MM-DD" 格式
    m = re.match(r"(\d{2})-(\d{2})", date_str)
    if m:
        return f"{now.year}-{m.group(1)}-{m.group(2)}"
    return None
