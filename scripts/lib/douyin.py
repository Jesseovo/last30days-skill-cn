"""抖音搜索模块 - 搜索抖音短视频内容。

Author: Jesse (https://github.com/Jesseovo)

支持三种模式（按优先级自动切换）：
1. TikHub API（需要 TIKHUB_API_KEY）
2. MediaCrawler 浏览器爬虫（需要 Playwright，无需 API Key）
3. 抖音公开搜索接口
"""

import json
import re
import sys
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from . import dates, relevance

_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15"


def search_douyin(
    topic: str,
    from_date: str,
    to_date: str,
    depth: str = "default",
    token: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """搜索抖音视频。

    Args:
        topic: 搜索关键词
        from_date: 起始日期
        to_date: 结束日期
        depth: 搜索深度
        token: TikHub API key 或抖音 API token

    Returns:
        抖音视频列表
    """
    limit_map = {"quick": 10, "default": 20, "deep": 40}
    limit = limit_map.get(depth, 20)

    items: List[Dict[str, Any]] = []

    if token:
        items = _search_via_tikhub(topic, limit, token)

    if not items:
        try:
            from . import crawler_bridge
            if crawler_bridge.is_playwright_available():
                sys.stderr.write("[抖音] 尝试 MediaCrawler 爬虫模式...\n")
                items = crawler_bridge.crawl_douyin(topic, limit)
                if items:
                    sys.stderr.write(f"[抖音] 爬虫模式获取 {len(items)} 条结果\n")
        except Exception as e:
            sys.stderr.write(f"[抖音] 爬虫模式失败: {e}\n")

    if not items:
        items = _search_via_public(topic, limit)

    if not items:
        items = _search_via_site_search(topic, limit)

    scored = []
    for i, item in enumerate(items):
        text = item.get("text", "")
        rel = relevance.token_overlap_relevance(topic, text)
        item["id"] = f"DY{i+1}"
        item["relevance"] = rel
        item["why_relevant"] = f"抖音视频：{text[:50]}"
        scored.append(item)

    scored.sort(key=lambda x: x.get("relevance", 0), reverse=True)
    return scored[:limit]


def _search_via_tikhub(topic: str, limit: int, token: str) -> List[Dict[str, Any]]:
    """通过 TikHub API 搜索抖音。"""
    items = []
    try:
        encoded = urllib.parse.quote(topic)
        url = f"https://api.tikhub.io/api/v1/douyin/web/fetch_general_search?keyword={encoded}&count={limit}&sort_type=0"
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("User-Agent", _UA)
        with urllib.request.urlopen(req, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))

        for v in data.get("data", {}).get("data", []):
            aweme = v.get("aweme_info", v)
            items.append(_parse_aweme(aweme))
    except Exception as e:
        sys.stderr.write(f"[抖音] TikHub 搜索失败: {e}\n")
    return items


def _search_via_public(topic: str, limit: int) -> List[Dict[str, Any]]:
    """通过抖音公开搜索接口（备用方案）。"""
    items = []
    try:
        encoded = urllib.parse.quote(topic)
        url = f"https://www.douyin.com/aweme/v1/web/general/search/single/?keyword={encoded}&count={min(limit, 20)}&search_channel=aweme_general&sort_type=0&publish_time=0"
        headers = {"User-Agent": _UA, "Referer": "https://www.douyin.com/"}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))

        for v in data.get("data", []):
            aweme = v.get("aweme_info", v)
            items.append(_parse_aweme(aweme))
    except Exception as e:
        sys.stderr.write(f"[抖音] 公开接口搜索失败: {e}\n")
    return items


def _fetch_html(url: str, timeout: int = 8) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "identity",
        "Referer": "https://cn.bing.com/",
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def _clean_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text or "")
    return re.sub(r"\s+", " ", text).strip()


def _search_via_site_search(topic: str, limit: int) -> List[Dict[str, Any]]:
    """官方接口/爬虫无结果时，用公开搜索引擎兜底获取抖音公开链接。"""
    items: List[Dict[str, Any]] = []
    try:
        query = f"site:douyin.com/video {topic}"
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
            if "douyin.com" not in href or href in seen:
                continue
            seen.add(href)
            title = _clean_text(title_match.group(2))
            snip_match = re.search(r"<p[^>]*>([\s\S]*?)</p>", block, re.S)
            snippet = _clean_text(snip_match.group(1)) if snip_match else ""
            text = f"{title} {snippet}".strip() if snippet else title
            items.append({
                "text": text,
                "url": href,
                "author_name": "",
                "author_id": "",
                "date": None,
                "engagement": {"views": 0, "likes": 0, "comments": 0, "shares": 0},
                "hashtags": re.findall(r"#([^#\s]+)#?", text),
                "duration": 0,
                "source": "site-search-fallback",
            })
            if len(items) >= limit:
                break
    except Exception as e:
        sys.stderr.write(f"[抖音] 站内搜索兜底失败: {e}\n")
    if items:
        sys.stderr.write(f"[抖音] 官方接口/爬虫无结果，已用公开搜索兜底获取 {len(items)} 条公开链接。\n")
    return items


def _parse_aweme(aweme: dict) -> Dict[str, Any]:
    """解析抖音视频数据。"""
    desc = aweme.get("desc", "")
    author = aweme.get("author", {})
    stats = aweme.get("statistics", {})
    create_time = aweme.get("create_time", 0)
    date_str = None
    if create_time:
        date_str = dates.timestamp_to_date(create_time)

    aweme_id = aweme.get("aweme_id", "")
    hashtags = []
    for tag in aweme.get("text_extra", []):
        if tag.get("hashtag_name"):
            hashtags.append(tag["hashtag_name"])

    return {
        "text": desc,
        "url": f"https://www.douyin.com/video/{aweme_id}" if aweme_id else "",
        "author_name": author.get("nickname", ""),
        "author_id": author.get("uid", ""),
        "date": date_str,
        "engagement": {
            "views": stats.get("play_count", 0),
            "likes": stats.get("digg_count", 0),
            "comments": stats.get("comment_count", 0),
            "shares": stats.get("share_count", 0),
        },
        "hashtags": hashtags,
        "duration": aweme.get("duration", 0),
    }
