"""小红书搜索模块 - 搜索小红书笔记。

Author: Jesse (https://github.com/Jesseovo)

支持多种数据获取方式（按优先级自动切换）：
1. xiaohongshu-mcp HTTP API（自托管，可选）
2. MediaCrawler 浏览器爬虫（基于 Playwright，无需 API Key）
3. 公开搜索接口（命中率较低，仅作兜底）

注意：v2.1 起已移除 ScrapeCreators 集成 —— ScrapeCreators 官方
（https://docs.scrapecreators.com）并未提供小红书端点，原代码调用的
`/v2/xiaohongshu/search` 始终返回 404，属于错误实现。
"""

import json
import re
import sys
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from . import dates, http, relevance

_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15"
_DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

_SCRAPECREATORS_DEPRECATION_WARNED = False


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
        token: 已弃用 —— 保留参数仅为向后兼容（v2.1 移除 ScrapeCreators 集成）
        api_base: xiaohongshu-mcp 自托管 HTTP API 地址（可选）

    Returns:
        小红书笔记列表
    """
    limit_map = {"quick": 10, "default": 20, "deep": 40}
    limit = limit_map.get(depth, 20)

    if token:
        global _SCRAPECREATORS_DEPRECATION_WARNED
        if not _SCRAPECREATORS_DEPRECATION_WARNED:
            sys.stderr.write(
                "[小红书] 警告：ScrapeCreators 集成已在 v2.1 移除（官方未提供小红书端点），"
                "传入的 token 已被忽略。请安装 Playwright 使用爬虫模式。\n"
            )
            _SCRAPECREATORS_DEPRECATION_WARNED = True

    items: List[Dict[str, Any]] = []

    if api_base:
        items = _search_via_mcp(topic, from_date, to_date, limit, api_base)

    if not items and depth != "quick":
        try:
            from . import crawler_bridge
            if crawler_bridge.is_playwright_available():
                sys.stderr.write("[小红书] 尝试 MediaCrawler 爬虫模式...\n")
                items = crawler_bridge.crawl_xiaohongshu(topic, limit)
                if items:
                    sys.stderr.write(f"[小红书] 爬虫模式获取 {len(items)} 条结果\n")
        except Exception as e:
            sys.stderr.write(f"[小红书] 爬虫模式失败: {e}\n")

    if not items:
        items = _search_via_public(topic, limit)

    if not items:
        items = _search_via_site_search(topic, limit)

    scored = []
    for i, item in enumerate(items):
        title = item.get("title", "")
        desc = item.get("desc", "")
        combined = f"{title} {desc}"
        rel = relevance.token_overlap_relevance(topic, combined)
        item["id"] = f"XHS{i+1}"
        item["relevance"] = rel
        source = item.get("source", "xiaohongshu")
        item["why_relevant"] = f"小红书来源({source}): {title[:50]}"
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
        resp = http.get(url, timeout=8, retries=1)
        if isinstance(resp, dict) and resp.get("data"):
            for note in resp["data"].get("items", resp["data"] if isinstance(resp["data"], list) else []):
                items.append(_parse_note(note))
    except Exception as e:
        sys.stderr.write(f"[小红书] MCP API 搜索失败: {e}\n")
    return items


def _search_via_public(topic: str, limit: int) -> List[Dict[str, Any]]:
    """通过公开接口搜索小红书（备用方案，命中率较低）。"""
    items = []
    try:
        encoded = urllib.parse.quote(topic)
        url = f"https://www.xiaohongshu.com/fe_api/burdock/weixin/v2/search/notes?keyword={encoded}&page=1&page_size={limit}"
        headers = {"User-Agent": _UA}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as response:
            data = json.loads(response.read().decode("utf-8"))
        for note in data.get("data", {}).get("notes", []):
            items.append(_parse_note(note))
    except Exception as e:
        sys.stderr.write(f"[小红书] 公开接口搜索失败: {e}\n")
    return items


def _fetch_html(url: str, timeout: int = 8) -> str:
    headers = {
        "User-Agent": _DESKTOP_UA,
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
    """Fallback to public web search when Xiaohongshu blocks API/Playwright."""
    items: List[Dict[str, Any]] = []
    try:
        query = f"site:xiaohongshu.com/explore {topic}"
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
            if "xiaohongshu.com" not in href or href in seen:
                continue
            seen.add(href)
            title = _clean_text(title_match.group(2))
            snip_match = re.search(r"<p[^>]*>([\s\S]*?)</p>", block, re.S)
            snippet = _clean_text(snip_match.group(1)) if snip_match else ""
            items.append({
                "title": title,
                "desc": snippet,
                "url": href,
                "author_name": "",
                "author_id": "",
                "date": None,
                "engagement": {"likes": 0, "collects": 0, "comments": 0, "shares": 0},
                "hashtags": re.findall(r"#([^#\s]+)#?", f"{title} {snippet}"),
                "images": [],
                "source": "site-search-fallback",
            })
            if len(items) >= limit:
                break
    except Exception as e:
        sys.stderr.write(f"[小红书] 站内搜索兜底失败: {e}\n")
    if items:
        sys.stderr.write(f"[小红书] 官方/Playwright 路径无结果，已用站内搜索兜底获取 {len(items)} 条公开链接。\n")
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

    hashtags = re.findall(r"#([^#\s]+)#?", f"{title} {desc}")

    date_str = note.get("time") or note.get("created_time") or note.get("date")
    if date_str and len(str(date_str)) == 13:
        date_str = dates.timestamp_to_date(int(date_str) / 1000)
    elif date_str and len(str(date_str)) == 10 and str(date_str).isdigit():
        date_str = dates.timestamp_to_date(int(date_str))

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
