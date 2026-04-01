"""百度搜索模块 - 替代 Exa/Brave 等 Web 搜索后端。

Author: Jesse (https://github.com/ChiTing111)

使用百度搜索 API 或公开搜索进行网页搜索。
"""

import json
import re
import sys
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from . import relevance

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def search_baidu(
    topic: str,
    from_date: str,
    to_date: str,
    depth: str = "default",
    api_key: Optional[str] = None,
    secret_key: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """搜索百度网页。

    Args:
        topic: 搜索关键词
        from_date: 起始日期
        to_date: 结束日期
        depth: 搜索深度
        api_key: 百度 API Key（可选）
        secret_key: 百度 Secret Key（可选）

    Returns:
        网页搜索结果列表
    """
    limit_map = {"quick": 10, "default": 20, "deep": 30}
    limit = limit_map.get(depth, 20)

    items: List[Dict[str, Any]] = []

    if api_key and secret_key:
        items = _search_via_api(topic, limit, api_key, secret_key)

    if not items:
        items = _search_via_public(topic, limit)

    scored = []
    for i, item in enumerate(items):
        title = item.get("title", "")
        snippet = item.get("snippet", "")
        combined = f"{title} {snippet}"
        rel = relevance.token_overlap_relevance(topic, combined)
        item["id"] = f"BD{i+1}"
        item["relevance"] = rel
        item["why_relevant"] = f"百度搜索：{title[:50]}"
        scored.append(item)

    scored.sort(key=lambda x: x.get("relevance", 0), reverse=True)
    return scored[:limit]


def _search_via_api(
    topic: str, limit: int, api_key: str, secret_key: str
) -> List[Dict[str, Any]]:
    """通过百度搜索 API 进行搜索。"""
    items = []
    try:
        encoded = urllib.parse.quote(topic)
        url = f"https://api.baidu.com/search/v1?q={encoded}&rn={limit}&key={api_key}"
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))

        for r in data.get("result", []):
            items.append({
                "title": _clean_html(r.get("title", "")),
                "snippet": _clean_html(r.get("abstract", "") or r.get("description", "")),
                "url": r.get("url", ""),
                "source_domain": _extract_domain(r.get("url", "")),
                "date": r.get("date"),
                "date_confidence": "med" if r.get("date") else "low",
            })
    except Exception as e:
        sys.stderr.write(f"[百度] API 搜索失败: {e}\n")
    return items


def _search_via_public(topic: str, limit: int) -> List[Dict[str, Any]]:
    """通过百度公开搜索（HTML 解析）。"""
    items = []
    try:
        encoded = urllib.parse.quote(topic)
        now_ts = int(time.time())
        ago_ts = now_ts - 30 * 86400
        url = f"https://www.baidu.com/s?wd={encoded}&rn={min(limit, 20)}&gpc=stf%3D{ago_ts}%2C{now_ts}%7Cstftype%3D1"
        headers = {
            "User-Agent": _UA,
            "Accept": "text/html",
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            html = response.read().decode("utf-8", errors="replace")

        results = re.findall(
            r'<h3[^>]*class="[^"]*t[^"]*"[^>]*>\s*<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
            html, re.S
        )
        snippets = re.findall(
            r'<span class="content-right_8Zs40">(.*?)</span>', html, re.S
        )

        for idx, (href, title_html) in enumerate(results[:limit]):
            title = re.sub(r"<[^>]+>", "", title_html).strip()
            snippet = ""
            if idx < len(snippets):
                snippet = re.sub(r"<[^>]+>", "", snippets[idx]).strip()

            items.append({
                "title": title,
                "snippet": snippet,
                "url": href,
                "source_domain": _extract_domain(href),
                "date": None,
                "date_confidence": "low",
            })
    except Exception as e:
        sys.stderr.write(f"[百度] 公开搜索失败: {e}\n")
    return items


def _clean_html(text: str) -> str:
    """清除 HTML 标签。"""
    return re.sub(r"<[^>]+>", "", text).strip()


def _extract_domain(url: str) -> str:
    """从 URL 中提取域名。"""
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc
    except Exception:
        return ""
