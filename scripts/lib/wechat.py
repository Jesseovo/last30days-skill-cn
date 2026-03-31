"""微信公众号搜索模块 - 搜索微信公众号文章。

Author: Jesse (https://github.com/ChiTing111)

使用搜狗微信搜索或第三方接口获取微信公众号文章。
"""

import json
import re
import sys
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from . import relevance

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def search_wechat(
    topic: str,
    from_date: str,
    to_date: str,
    depth: str = "default",
    api_key: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """搜索微信公众号文章。

    Args:
        topic: 搜索关键词
        from_date: 起始日期
        to_date: 结束日期
        depth: 搜索深度
        api_key: 第三方搜索 API key（可选）

    Returns:
        微信公众号文章列表
    """
    limit_map = {"quick": 8, "default": 15, "deep": 30}
    limit = limit_map.get(depth, 15)

    items: List[Dict[str, Any]] = []

    if api_key:
        items = _search_via_api(topic, limit, api_key)

    if not items:
        items = _search_via_sogou(topic, limit)

    scored = []
    for i, item in enumerate(items):
        title = item.get("title", "")
        snippet = item.get("snippet", "")
        combined = f"{title} {snippet}"
        rel = relevance.token_overlap_relevance(topic, combined)
        item["id"] = f"WX{i+1}"
        item["relevance"] = rel
        item["why_relevant"] = f"微信公众号：{title[:50]}"
        scored.append(item)

    scored.sort(key=lambda x: x.get("relevance", 0), reverse=True)
    return scored[:limit]


def _search_via_api(topic: str, limit: int, api_key: str) -> List[Dict[str, Any]]:
    """通过第三方 API 搜索微信公众号文章。"""
    items = []
    try:
        encoded = urllib.parse.quote(topic)
        url = f"https://api.jisuapi.com/weixin/search?keyword={encoded}&pagenum=1&pagesize={limit}&appkey={api_key}"
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))

        if data.get("status") == "0":
            for article in data.get("result", {}).get("list", []):
                items.append({
                    "title": article.get("name", ""),
                    "snippet": article.get("description", ""),
                    "url": article.get("url", ""),
                    "source_name": article.get("weixinname", ""),
                    "wechat_id": article.get("weixinhao", ""),
                    "date": article.get("date"),
                    "engagement": {},
                })
    except Exception as e:
        sys.stderr.write(f"[微信] API 搜索失败: {e}\n")
    return items


def _search_via_sogou(topic: str, limit: int) -> List[Dict[str, Any]]:
    """通过搜狗微信搜索。"""
    items = []
    try:
        encoded = urllib.parse.quote(topic)
        url = f"https://weixin.sogou.com/weixin?type=2&query={encoded}&ie=utf8"
        headers = {"User-Agent": _UA}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            html = response.read().decode("utf-8")

        titles = re.findall(r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', html, re.S)
        dates_found = re.findall(r'timeConvert\(\'(\d+)\'\)', html)
        accounts = re.findall(r'account="([^"]*)"', html)

        for idx, (href, title_html) in enumerate(titles[:limit]):
            if "weixin.qq.com" not in href and "sogou.com" not in href:
                continue
            title = re.sub(r"<[^>]+>", "", title_html).strip()
            if not title:
                continue

            date_str = None
            if idx < len(dates_found):
                try:
                    from datetime import datetime
                    date_str = datetime.fromtimestamp(int(dates_found[idx])).strftime("%Y-%m-%d")
                except Exception:
                    pass

            items.append({
                "title": title,
                "snippet": "",
                "url": href,
                "source_name": accounts[idx] if idx < len(accounts) else "",
                "wechat_id": "",
                "date": date_str,
                "engagement": {},
            })
    except Exception as e:
        sys.stderr.write(f"[微信] 搜狗搜索失败: {e}\n")
    return items
