"""今日头条搜索模块 - 提供资讯搜索和热榜。

Author: Jesse (https://github.com/Jesseovo)

v4 数据路径：
1. ``so.toutiao.com/search``（资讯频道）服务端渲染页：页面内嵌每条结果的 JSON
   卡片（标题、来源、发布时间、阅读/评论/点赞数），无需 ``_signature``。
   旧的 ``/api/search/content/`` 已恒返回空，v4 起移除。
2. 头条热榜（``hot-event/hot-board``）中与主题相关的条目。
3. 公开搜索引擎 ``site:toutiao.com`` 兜底（经 URL 与相关性校验）。
"""

import json
import re
import sys
import time
import urllib.parse
from datetime import datetime
from typing import Any, Dict, List, Optional

from . import dates, http, relevance, websearch

SO_SEARCH_URL = "https://so.toutiao.com/search"
HOT_BOARD_URL = "https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc"
ARTICLE_URL_PATTERN = r"toutiao\.com/(?:article|group|w|video|a\d)"

_CARD_RE = re.compile(r'<script[^>]*type="application/json"[^>]*>(\{"data":[\s\S]*?)</script>')


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
    pages = {"quick": 1, "default": 2, "deep": 3}.get(depth, 2)

    items: List[Dict[str, Any]] = []
    errors: List[str] = []

    for page in range(pages):
        try:
            page_items = _search_via_so(topic, page)
        except Exception as exc:
            errors.append(str(exc))
            sys.stderr.write(f"[今日头条] 资讯搜索失败（第 {page + 1} 页）: {exc}\n")
            break
        items.extend(page_items)
        if len(page_items) < 5:
            break

    if depth != "quick":
        try:
            hot_items = _get_hot_related(topic)
        except Exception as exc:
            hot_items = []
            sys.stderr.write(f"[今日头条] 热榜获取失败: {exc}\n")
        existing_titles = {it.get("title", "").lower() for it in items}
        for hi in hot_items:
            if hi.get("title", "").lower() not in existing_titles:
                items.append(hi)

    if not items:
        items = _search_via_site_search(topic, limit)

    if not items and errors:
        raise http.HTTPError("头条搜索失败：" + errors[0] + "；" + websearch.describe_failure("头条"))

    items = _dedupe(items)
    scored = []
    for item in items:
        title = item.get("title", "")
        abstract = item.get("abstract", "")
        rel = relevance.token_overlap_relevance(topic, f"{title} {abstract}")
        item["relevance"] = rel
        src = item.get("source_name") or "今日头条"
        item["why_relevant"] = f"今日头条（{src}）：{title[:50]}"
        scored.append(item)

    scored.sort(key=lambda x: x.get("relevance", 0), reverse=True)
    scored = scored[:limit]
    for i, item in enumerate(scored):
        item["id"] = f"TT{i+1}"
    return scored


def _dedupe(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out = []
    for item in items:
        key = (item.get("url") or "").split("?", 1)[0] or item.get("title")
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _search_via_so(topic: str, page: int = 0) -> List[Dict[str, Any]]:
    params = {
        "keyword": topic,
        "pd": "information",
        "dvpf": "pc",
        "source": "input",
    }
    if page:
        params["page_num"] = str(page)
    url = f"{SO_SEARCH_URL}?{urllib.parse.urlencode(params)}"
    headers = http.browser_headers(referer="https://so.toutiao.com/")
    # so.toutiao.com occasionally serves a client-rendered shell without the
    # embedded result cards (~1 in 8 requests); retry a couple of times.
    for attempt in range(3):
        _status, final_url, body = http.fetch(url, headers=headers, timeout=15)
        if "verify" in final_url or ("captcha" in body[:4000] and "druid-card-data" not in body):
            raise http.HTTPError("头条搜索触发验证页")
        cards = parse_so_html(body)
        if cards or _looks_like_empty_result(body):
            return cards
        http.log(f"[今日头条] 第 {attempt + 1} 次请求只拿到页面壳，重试")
        time.sleep(0.8 * (attempt + 1))
    return []


def _looks_like_empty_result(body: str) -> bool:
    """True when the SERP genuinely has no results (vs. an empty shell)."""
    return "没有找到" in body or "无相关结果" in body or "抱歉，未找到" in body


def parse_so_html(body: str) -> List[Dict[str, Any]]:
    """Parse the JSON result cards embedded in so.toutiao.com SERP HTML."""
    items: List[Dict[str, Any]] = []
    for raw in _CARD_RE.findall(body or ""):
        try:
            card = json.loads(raw)
        except ValueError:
            continue
        parsed = _parse_card((card or {}).get("data") or {})
        if parsed:
            items.append(parsed)
    return items


def _to_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _card_date(data: Dict[str, Any]) -> Optional[str]:
    text = data.get("datetime")
    if isinstance(text, str) and len(text) >= 10:
        try:
            return datetime.strptime(text[:10], "%Y-%m-%d").date().isoformat()
        except ValueError:
            pass
    for key in ("publish_time", "display_time", "behot_time", "create_time"):
        value = data.get(key)
        if value:
            try:
                return dates.timestamp_to_date(int(value))
            except (TypeError, ValueError):
                continue
    return None


def _parse_card(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    title = _clean_html(data.get("title") or "")
    if not title:
        return None
    group_id = str(data.get("group_id") or data.get("item_id") or "").strip()
    info = data.get("info") or {}
    toutiao_url = info.get("url") if isinstance(info, dict) else ""
    if not toutiao_url and group_id.isdigit():
        toutiao_url = f"https://www.toutiao.com/group/{group_id}/"
    article_url = data.get("article_url") or data.get("display_url") or ""
    url = toutiao_url or article_url
    if url and url.startswith("//"):
        url = "https:" + url
    summary = data.get("summary")
    abstract = data.get("abstract") or (summary.get("text") if isinstance(summary, dict) else "") or ""
    return {
        "title": title,
        "abstract": _clean_html(abstract),
        "url": url,
        "original_url": article_url,
        "source_name": data.get("source") or data.get("media_name") or "",
        "date": _card_date(data),
        "engagement": {
            "comments": _to_int(data.get("comment_count")),
            "likes": _to_int(data.get("digg_count")),
            "reads": _to_int(data.get("read_count")),
        },
        "source": "so.toutiao",
    }


def fetch_hot(limit: int = 50) -> List[Dict[str, Any]]:
    """头条热榜（热榜模式与主题匹配共用）。"""
    data = http.get(
        HOT_BOARD_URL,
        headers=http.browser_headers(referer="https://www.toutiao.com/", accept="json"),
        timeout=10,
        retries=1,
    )
    out = []
    for idx, entry in enumerate((data or {}).get("data") or [], start=1):
        title = entry.get("Title") or ""
        if not title:
            continue
        out.append({
            "rank": idx,
            "title": title,
            "url": entry.get("Url") or "",
            "hot_value": _to_int(entry.get("HotValue")) or None,
            "label": entry.get("Label") or "",
            "abstract": entry.get("Abstract") or "",
        })
        if len(out) >= limit:
            break
    return out


def _get_hot_related(topic: str) -> List[Dict[str, Any]]:
    """从头条热榜中查找与主题相关的话题。"""
    items = []
    for entry in fetch_hot(50):
        title = entry["title"]
        if relevance.token_overlap_relevance(topic, title) < 0.35:
            continue
        items.append({
            "title": title,
            "abstract": entry.get("abstract", ""),
            "url": entry.get("url", ""),
            "source_name": "今日头条热榜",
            "date": None,
            "is_hot": True,
            "hot_value": entry.get("hot_value"),
            "engagement": {"hot_value": entry.get("hot_value")},
            "source": "hot-board",
        })
    return items


def _search_via_site_search(topic: str, limit: int) -> List[Dict[str, Any]]:
    """资讯搜索/热榜无结果时，用公开搜索引擎兜底获取头条公开链接。"""
    items: List[Dict[str, Any]] = []
    for result in websearch.site_search(
        "toutiao.com", topic, limit=limit, url_pattern=ARTICLE_URL_PATTERN, label="今日头条"
    ):
        items.append({
            "title": result.title,
            "abstract": result.snippet,
            "url": result.url,
            "source_name": "今日头条",
            "date": result.date,
            "engagement": {},
            "source": f"site-search:{result.engine}",
        })
    if items:
        sys.stderr.write(f"[今日头条] 资讯搜索/热榜无结果，已用公开搜索兜底获取 {len(items)} 条公开链接。\n")
    return items


def _clean_html(text: str) -> str:
    """清除 HTML 标签与高亮。"""
    text = re.sub(r"<[^>]+>", "", text or "")
    return re.sub(r"\s+", " ", text).strip()
