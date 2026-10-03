"""抖音搜索模块 - 搜索抖音短视频内容。

Author: Jesse (https://github.com/Jesseovo)

v4 数据路径（按优先级自动切换）：
1. TikHub API（``TIKHUB_API_KEY``）。
2. Playwright 浏览器（复用 ``login douyin`` 的登录态，拦截搜索 XHR）。
3. 抖音热榜中与主题相关的热点（匿名可用）。
4. ``site:douyin.com`` 公开搜索兜底（仅接受视频/图文链接，带相关性校验）。

v4 移除了 ``/aweme/v1/web/general/search/single/`` 匿名直连：该接口强制
``a_bogus`` 签名，匿名请求恒返回空 ``data``，只会白白消耗数秒。
"""

import re
import sys
import urllib.parse
from datetime import datetime
from typing import Any, Dict, List, Optional

from . import dates, http, relevance, websearch

HOT_LIST_URL = (
    "https://www.douyin.com/aweme/v1/web/hot/search/list/"
    "?device_platform=webapp&aid=6383&channel=channel_pc_web&detail_list=1"
)
VIDEO_URL_PATTERN = r"douyin\.com/(?:video|note)/\d+"
LOGIN_HINT = (
    "抖音网页搜索需要签名或登录：配置 TIKHUB_API_KEY，或运行 "
    "`python scripts/last30days.py login douyin`（需 Playwright）保存登录态"
)


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
    attempted: List[str] = []

    if token:
        attempted.append("TikHub")
        items = _search_via_tikhub(topic, limit, token)

    if not items:
        try:
            from . import crawler_bridge
            if crawler_bridge.is_playwright_available():
                attempted.append("Playwright")
                sys.stderr.write("[抖音] 尝试浏览器爬虫模式...\n")
                items = crawler_bridge.crawl_douyin(topic, limit)
                if items:
                    sys.stderr.write(f"[抖音] 爬虫模式获取 {len(items)} 条结果\n")
        except Exception as e:
            sys.stderr.write(f"[抖音] 爬虫模式失败: {e}\n")

    if not items:
        attempted.append("热榜/公开搜索")
        hot = _search_hot_related(topic)
        site = _search_via_site_search(topic, limit)
        items = hot + site
        if items:
            sys.stderr.write(
                f"[抖音] 平台搜索不可用，已用热榜/公开搜索兜底获取 {len(items)} 条"
                f"（热榜 {len(hot)}，公开链接 {len(site)}）。\n"
            )

    if not items:
        raise http.HTTPError(
            "未获取到抖音结果；已尝试：" + " / ".join(attempted) + "。" + LOGIN_HINT + "。"
            + websearch.describe_failure("抖音")
        )

    scored = []
    for item in items:
        text = item.get("text", "")
        if "relevance" not in item:
            item["relevance"] = relevance.token_overlap_relevance(topic, text, hashtags=item.get("hashtags"))
        item.setdefault("why_relevant", f"抖音视频：{text[:50]}")
        scored.append(item)

    scored.sort(key=lambda x: x.get("relevance", 0), reverse=True)
    scored = scored[:limit]
    for i, item in enumerate(scored):
        item["id"] = f"DY{i+1}"
    return scored


def _search_via_tikhub(topic: str, limit: int, token: str) -> List[Dict[str, Any]]:
    """通过 TikHub API 搜索抖音。"""
    items = []
    try:
        encoded = urllib.parse.quote(topic)
        url = f"https://api.tikhub.io/api/v1/douyin/web/fetch_general_search?keyword={encoded}&count={limit}&sort_type=0"
        data = http.get(
            url,
            headers={"Authorization": f"Bearer {token}", "User-Agent": http.USER_AGENT},
            timeout=25,
            retries=2,
        )
        for v in ((data.get("data") or {}).get("data") or []):
            aweme = v.get("aweme_info", v) if isinstance(v, dict) else None
            if isinstance(aweme, dict):
                items.append(parse_aweme(aweme, source="tikhub"))
    except Exception as e:
        sys.stderr.write(f"[抖音] TikHub 搜索失败: {e}\n")
    return items


def fetch_hot(limit: int = 50) -> List[Dict[str, Any]]:
    """抖音热榜（匿名可用）。"""
    data = http.get(
        HOT_LIST_URL,
        headers=http.browser_headers(referer="https://www.douyin.com/", accept="json"),
        timeout=10,
        retries=1,
    )
    out = []
    for idx, entry in enumerate(((data or {}).get("data") or {}).get("word_list") or [], start=1):
        word = entry.get("word") or ""
        if not word:
            continue
        sentence_id = entry.get("sentence_id")
        url = (
            f"https://www.douyin.com/hot/{sentence_id}"
            if sentence_id
            else f"https://www.douyin.com/search/{urllib.parse.quote(word)}"
        )
        out.append({
            "rank": entry.get("position") or idx,
            "title": word,
            "url": url,
            "hot_value": entry.get("hot_value"),
            "label": "",
            "event_time": entry.get("event_time"),
        })
        if len(out) >= limit:
            break
    return out


def _search_hot_related(topic: str) -> List[Dict[str, Any]]:
    try:
        hot = fetch_hot(50)
    except Exception as exc:
        http.log(f"[抖音] 热榜获取失败: {exc}")
        return []
    items = []
    for entry in hot:
        rel = relevance.token_overlap_relevance(topic, entry["title"])
        if rel < 0.35:
            continue
        event_date = dates.timestamp_to_date(entry["event_time"]) if entry.get("event_time") else None
        items.append({
            "text": entry["title"],
            "url": entry["url"],
            "author_name": "抖音热榜",
            "author_id": "",
            "date": event_date or datetime.now(dates.CST).strftime("%Y-%m-%d"),
            "engagement": None,
            "hashtags": [],
            "duration": None,
            "relevance": rel,
            "why_relevant": f"抖音热榜第 {entry['rank']} 位，热度 {entry.get('hot_value') or '未知'}",
            "source": "hot-list",
        })
    return items


def _search_via_site_search(topic: str, limit: int) -> List[Dict[str, Any]]:
    """官方接口/爬虫无结果时，用公开搜索引擎兜底获取抖音公开链接。"""
    items: List[Dict[str, Any]] = []
    for result in websearch.site_search(
        "douyin.com", topic, limit=min(limit, 10), url_pattern=VIDEO_URL_PATTERN, label="抖音"
    ):
        text = f"{result.title} {result.snippet}".strip()
        items.append({
            "text": text,
            "url": result.url,
            "author_name": "",
            "author_id": "",
            "date": result.date,
            "engagement": None,
            "hashtags": re.findall(r"#([^#\s]+)#?", text)[:10],
            "duration": None,
            "source": f"site-search:{result.engine}",
        })
    return items


def parse_aweme(aweme: dict, source: str = "api") -> Dict[str, Any]:
    """解析抖音视频数据（TikHub / 网页 XHR 共用）。"""
    desc = aweme.get("desc", "") or ""
    author = aweme.get("author", {}) or {}
    stats = aweme.get("statistics", {}) or {}
    create_time = aweme.get("create_time", 0)
    date_str = dates.timestamp_to_date(create_time) if create_time else None
    aweme_id = aweme.get("aweme_id", "")
    hashtags = [tag["hashtag_name"] for tag in (aweme.get("text_extra") or []) if isinstance(tag, dict) and tag.get("hashtag_name")]
    duration = aweme.get("duration") or (aweme.get("video") or {}).get("duration") or 0
    try:
        duration = int(duration)
    except (TypeError, ValueError):
        duration = 0
    if duration > 1000:  # milliseconds
        duration //= 1000
    return {
        "text": desc,
        "url": f"https://www.douyin.com/video/{aweme_id}" if aweme_id else "",
        "author_name": author.get("nickname", ""),
        "author_id": str(author.get("uid", "") or author.get("sec_uid", "")),
        "date": date_str,
        "engagement": {
            "views": stats.get("play_count", 0),
            "likes": stats.get("digg_count", 0),
            "comments": stats.get("comment_count", 0),
            "shares": stats.get("share_count", 0),
        },
        "hashtags": hashtags,
        "duration": duration or None,
        "source": source,
    }


# Backward-compatible alias (v3 name).
_parse_aweme = parse_aweme
