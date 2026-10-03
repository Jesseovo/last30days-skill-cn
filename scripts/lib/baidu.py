"""百度搜索模块 - 中文网页搜索后端。

Author: Jesse (https://github.com/Jesseovo)

v4 数据路径：
1. 百度千帆「AI 搜索」``web_search`` API（``BAIDU_API_KEY``，Bearer 鉴权，
   ``search_recency_filter`` 限定时间窗）。v3 调用的 ``api.baidu.com/search/v1``
   并不是公开 API，v4 起替换为官方接口；``BAIDU_SECRET_KEY`` 不再需要（兼容保留）。
2. 百度网页搜索 HTML（解析 ``mu`` 真实链接、来源站点与发布时间）。
3. 被「百度安全验证」拦截时，降级到多引擎公开搜索（websearch）。
"""

import re
import sys
import time
import urllib.parse
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from . import dates, http, relevance, websearch

QIANFAN_SEARCH_URL = "https://qianfan.baidubce.com/v2/ai_search/web_search"

_ANTIBOT_SIGNATURES = (
    "wappass.baidu.com",
    "百度安全验证",
    "百度智能云验证",
    "verify.baidu.com",
    "/static/verify",
)


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
        api_key: 百度千帆 API Key（可选，Bearer）
        secret_key: 已弃用，保留参数仅为兼容 v3 配置

    Returns:
        网页搜索结果列表
    """
    limit_map = {"quick": 10, "default": 20, "deep": 30}
    limit = limit_map.get(depth, 20)

    items: List[Dict[str, Any]] = []

    if api_key:
        items = _search_via_api(topic, limit, api_key, from_date, to_date)

    if not items:
        items = _search_via_public(topic, limit, from_date, to_date)

    if not items:
        items = _search_via_websearch(topic, limit)

    scored = []
    for item in items:
        title = item.get("title", "")
        snippet = item.get("snippet", "")
        rel = relevance.token_overlap_relevance(topic, f"{title} {snippet}")
        item["relevance"] = rel
        item["why_relevant"] = f"{item.get('source_tag', '百度搜索')}：{title[:50]}"
        scored.append(item)

    scored.sort(key=lambda x: x.get("relevance", 0), reverse=True)
    scored = scored[:limit]
    for i, item in enumerate(scored):
        item["id"] = f"BD{i+1}"
    return scored


def _recency_filter(from_date: str, to_date: str) -> str:
    try:
        span = (datetime.strptime(to_date, "%Y-%m-%d") - datetime.strptime(from_date, "%Y-%m-%d")).days
    except (TypeError, ValueError):
        return "month"
    if span <= 7:
        return "week"
    if span <= 31:
        return "month"
    if span <= 183:
        return "semiyear"
    return "year"


def _search_via_api(topic: str, limit: int, api_key: str, from_date: str, to_date: str) -> List[Dict[str, Any]]:
    """百度千帆 AI 搜索 web_search API。"""
    payload = {
        "messages": [{"role": "user", "content": topic}],
        "edition": "standard",
        "search_source": "baidu_search_v2",
        "resource_type_filter": [{"type": "web", "top_k": min(max(limit, 1), 50)}],
        "search_recency_filter": _recency_filter(from_date, to_date),
        "safe_search": False,
    }
    try:
        data = http.post(
            QIANFAN_SEARCH_URL,
            payload,
            headers={"Authorization": f"Bearer {api_key}", "X-Appbuilder-From": "last30days-cn"},
            timeout=20,
            retries=2,
        )
    except Exception as e:
        sys.stderr.write(f"[百度] 千帆搜索 API 失败: {e}\n")
        return []
    if isinstance(data, dict) and data.get("code") and not data.get("references"):
        sys.stderr.write(f"[百度] 千帆搜索 API 返回错误: {data.get('code')} {data.get('message', '')}\n")
        return []
    return parse_api_references(data)


def parse_api_references(data: Any) -> List[Dict[str, Any]]:
    items = []
    references = data.get("references") if isinstance(data, dict) else None
    for ref in references or []:
        if not isinstance(ref, dict):
            continue
        url = ref.get("url") or ""
        title = _clean_html(ref.get("title") or "")
        if not url or not title:
            continue
        date_value = _normalize_date(str(ref.get("date") or ref.get("publish_time") or ""))
        items.append({
            "title": title,
            "snippet": _clean_html(ref.get("content") or ref.get("snippet") or "")[:500],
            "url": url,
            "source_domain": ref.get("website") or ref.get("web_anchor") or _extract_domain(url),
            "date": date_value,
            "date_confidence": "high" if date_value else "low",
            "source_tag": "百度千帆API",
            "source": "qianfan-api",
        })
    return items


def _build_headers(referer: str) -> Dict[str, str]:
    return http.browser_headers(referer=referer)


def _is_antibot_page(html: str) -> bool:
    if not html:
        return True
    return any(sig in html for sig in _ANTIBOT_SIGNATURES)


def _fetch(url: str, headers: Dict[str, str], timeout: int = 15) -> str:
    return http.get_text(url, headers=headers, timeout=timeout)


def _search_via_public(topic: str, limit: int, from_date: Optional[str] = None, to_date: Optional[str] = None) -> List[Dict[str, Any]]:
    """通过百度公开搜索（HTML 解析）。"""
    try:
        now_ts = int(time.time())
        ago_ts = now_ts - 30 * 86400
        if from_date and to_date:
            try:
                ago_ts = int(datetime.strptime(from_date, "%Y-%m-%d").replace(tzinfo=dates.CST).timestamp())
                now_ts = int(datetime.strptime(to_date, "%Y-%m-%d").replace(tzinfo=dates.CST).timestamp()) + 86399
            except ValueError:
                pass
        params = {"wd": topic, "rn": str(min(limit, 20)), "gpc": f"stf={ago_ts},{now_ts}|stftype=1"}
        url = f"https://www.baidu.com/s?{urllib.parse.urlencode(params)}"
        html = _fetch(url, _build_headers("https://www.baidu.com/"))
    except Exception as e:
        sys.stderr.write(f"[百度] 公开搜索失败: {e}\n")
        return []

    if _is_antibot_page(html):
        sys.stderr.write(
            "[百度] 公开搜索被安全验证拦截，已自动降级到公开搜索引擎兜底。"
            "配置 BAIDU_API_KEY（千帆 AI 搜索）可获得稳定结果。\n"
        )
        return []
    return parse_baidu_html(html, limit)


def parse_baidu_html(html: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Parse Baidu SERP organic results (real URL via ``mu``, site, date).

    ``result-op`` containers are Baidu's own cards (百科/AI 应用/相关搜索/
    聚合新闻) and ``nourl.ubs.baidu.com`` placeholders — both are skipped, as
    are promoted (广告) blocks.
    """
    import html as html_lib

    items: List[Dict[str, Any]] = []
    containers = list(re.finditer(r'<div([^>]*class="([^"]*\bresult\b[^"]*c-container[^"]*)"[^>]*)>', html))
    for idx, match in enumerate(containers):
        start = match.end()
        end = containers[idx + 1].start() if idx + 1 < len(containers) else len(html)
        attrs = match.group(1)
        classes = match.group(2).split()
        block = html[start:end]
        if "result-op" in classes or "data-tuiguang" in attrs or "data-tuiguang" in block[:3000]:
            continue
        title_match = re.search(r'<h3[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>([\s\S]*?)</a>', block)
        if not title_match:
            continue
        mu_match = re.search(r'\bmu="([^"]+)"', attrs)
        real_url = html_lib.unescape(mu_match.group(1)) if mu_match else ""
        if real_url.startswith("http://nourl.") or not real_url.startswith("http"):
            real_url = ""
        href = html_lib.unescape(title_match.group(1))
        url = real_url or href
        title = _clean_html(title_match.group(2))
        if not title:
            continue

        snippet = _baidu_summary(block)
        if not snippet:
            for pattern in (
                r'<span[^>]*class="[^"]*content-right_[^"]*"[^>]*>([\s\S]*?)</span>',
                r'<span[^>]*class="[^"]*c-font-normal[^"]*"[^>]*>([\s\S]*?)</span>',
                r'<div[^>]*class="[^"]*c-abstract[^"]*"[^>]*>([\s\S]*?)</div>',
            ):
                snip_match = re.search(pattern, block)
                if snip_match:
                    snippet = _clean_html(snip_match.group(1))
                    break

        site_match = (
            re.search(r'<span[^>]*class="[^"]*cosc-source-text[^"]*"[^>]*>([\s\S]*?)</span>', block)
            or re.search(r'<span[^>]*class="[^"]*c-color-gray(?!2)[^"]*"[^>]*>([\s\S]*?)</span>', block)
        )
        site = _clean_html(site_match.group(1)) if site_match else ""
        time_match = re.search(r'<span[^>]*class="[^"]*(?:prefix-time|c-color-gray2)[^"]*"[^>]*>([^<]{2,30})</span>', block)
        date_value = _find_date(time_match.group(1)) if time_match else None
        if not date_value:
            visible = _clean_html(re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", block))
            date_value = _find_date(visible[:1500])
        items.append({
            "title": title,
            "snippet": snippet,
            "url": url,
            "source_domain": site or _extract_domain(real_url) or _extract_domain(href),
            "date": date_value,
            "date_confidence": "med" if date_value else "low",
            "source_tag": "百度",
            "source": "baidu-web",
        })
        if len(items) >= limit:
            break
    return items


def _baidu_summary(block: str) -> str:
    """Abstract text of a 2025+ Baidu result (``summary-text_*`` span with nested <em>)."""
    match = re.search(r'<span[^>]*class="[^"]*summary-text[^"]*"[^>]*>', block)
    if not match:
        return ""
    tail = block[match.end():match.end() + 2000]
    for stop in ("</div>", "<div"):
        cut = tail.find(stop)
        if cut > 0:
            tail = tail[:cut]
    return _clean_html(tail)[:300]


def _search_via_websearch(topic: str, limit: int) -> List[Dict[str, Any]]:
    """百度不可用时的多引擎公开搜索兜底。"""
    items: List[Dict[str, Any]] = []
    for result in websearch.search(topic, limit=limit, topic=topic, label="百度"):
        items.append({
            "title": result.title,
            "snippet": result.snippet,
            "url": result.url,
            "source_domain": _extract_domain(result.url),
            "date": result.date,
            "date_confidence": "med" if result.date else "low",
            "source_tag": f"{result.engine}兜底",
            "source": f"websearch:{result.engine}",
        })
    if items:
        sys.stderr.write(f"[百度] 已用公开搜索引擎兜底获取 {len(items)} 条网页结果。\n")
    return items


# Backward-compatible name used by v3 tests/callers.
_search_via_bing = _search_via_websearch


HOT_BOARD_HTML = "https://top.baidu.com/board?tab=realtime"
HOT_BOARD_API = "https://top.baidu.com/api/board?platform=wise&tab=realtime"
_HOT_TAGS = {"1": "新", "3": "热"}


def fetch_hot(limit: int = 50) -> List[Dict[str, Any]]:
    """百度热搜（PC 页内嵌 s-data，失败时回退移动端接口）。"""
    import json as json_mod

    entries: List[Dict[str, Any]] = []
    try:
        body = http.get_text(HOT_BOARD_HTML, headers=http.browser_headers(referer="https://top.baidu.com/"), timeout=12)
        match = re.search(r"<!--s-data:([\s\S]*?)-->", body)
        if match:
            data = json_mod.loads(match.group(1))
            for card in ((data.get("data") or {}).get("cards") or []):
                entries.extend(card.get("content") or [])
    except Exception as exc:
        http.log(f"[百度] 热搜 PC 页解析失败: {exc}")
    if not entries:
        data = http.get(HOT_BOARD_API, headers=http.browser_headers(kind="mobile", referer="https://top.baidu.com/", accept="json"), timeout=10, retries=1)
        for card in ((data or {}).get("data") or {}).get("cards") or []:
            for block in card.get("content") or []:
                entries.extend(block.get("content") or [] if isinstance(block, dict) else [])

    out = []
    for entry in entries:
        word = entry.get("word") or entry.get("query") or ""
        if not word:
            continue
        label = "置顶" if entry.get("isTop") else _HOT_TAGS.get(str(entry.get("hotTag")), "") or entry.get("newHotName", "") or ""
        try:
            hot_value = int(entry.get("hotScore")) if entry.get("hotScore") else None
        except (TypeError, ValueError):
            hot_value = None
        out.append({
            "rank": len(out) + 1,
            "title": word,
            "url": entry.get("rawUrl") or entry.get("url") or f"https://www.baidu.com/s?wd={urllib.parse.quote(word)}",
            "hot_value": hot_value,
            "label": label,
            "desc": _clean_html(entry.get("desc") or "")[:200],
            "pinned": bool(entry.get("isTop")),
        })
        if len(out) >= limit:
            break
    return out


_RELATIVE_PATTERNS = (
    (re.compile(r"(\d+)\s*分钟前"), "minutes"),
    (re.compile(r"(\d+)\s*小时前"), "hours"),
    (re.compile(r"(\d+)\s*天前"), "days"),
)


def _find_date(text: str) -> Optional[str]:
    now = datetime.now(dates.CST)
    for pattern, unit in _RELATIVE_PATTERNS:
        match = pattern.search(text)
        if match:
            return (now - timedelta(**{unit: int(match.group(1))})).strftime("%Y-%m-%d")
    if "昨天" in text:
        return (now - timedelta(days=1)).strftime("%Y-%m-%d")
    return _normalize_date(text)


def _normalize_date(text: str) -> Optional[str]:
    if not text:
        return None
    match = re.search(r"(20\d{2})[年\-/.](\d{1,2})[月\-/.](\d{1,2})", text)
    if not match:
        return None
    year, month, day = (int(g) for g in match.groups())
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return None
    return f"{year:04d}-{month:02d}-{day:02d}"


def _clean_html(text: str) -> str:
    """清除 HTML 标签。"""
    text = re.sub(r"<[^>]+>", "", text or "")
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&quot;", '"')
    return re.sub(r"\s+", " ", text).strip()


def _extract_domain(url: str) -> str:
    """从 URL 中提取域名。"""
    try:
        netloc = urllib.parse.urlparse(url).netloc
        return "" if netloc.endswith("baidu.com") else netloc
    except Exception:
        return ""
