"""微信公众号搜索模块 - 搜索微信公众号文章。

Author: Jesse (https://github.com/Jesseovo)

v4：
- 修复搜狗微信解析：旧实现把页面上所有 ``<a>`` 链接（"图片"、"知乎"、"医疗"
  等导航入口）当成文章，日期也按下标错位。现在只解析 ``ul.news-list`` 中的
  结果卡片（标题 / 摘要 / 公众号 / 发布时间）。
- 搜狗反爬页会被识别并如实报错，随后尝试 ``site:mp.weixin.qq.com`` 公开搜索兜底。
"""

import html as html_lib
import re
import sys
import time
import urllib.parse
from typing import Any, Dict, List, Optional

from . import dates, http, relevance, websearch

SOGOU_BASE = "https://weixin.sogou.com"
ARTICLE_URL_PATTERN = r"mp\.weixin\.qq\.com/s"


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
        api_key: 第三方搜索 API key（可选，极速数据 jisuapi）

    Returns:
        微信公众号文章列表
    """
    limit_map = {"quick": 8, "default": 15, "deep": 30}
    limit = limit_map.get(depth, 15)
    pages = {"quick": 1, "default": 1, "deep": 2}.get(depth, 1)

    items: List[Dict[str, Any]] = []
    errors: List[str] = []

    if api_key:
        items = _search_via_api(topic, limit, api_key)

    if not items:
        for page in range(1, pages + 1):
            try:
                page_items = _search_via_sogou(topic, page)
            except http.HTTPError as exc:
                errors.append(str(exc))
                sys.stderr.write(f"[微信] 搜狗搜索失败: {exc}\n")
                break
            items.extend(page_items)
            if not page_items:
                break
            if page < pages:
                time.sleep(1.5)

    if not items:
        fallback = websearch.site_search(
            "mp.weixin.qq.com", topic, limit=limit, url_pattern=ARTICLE_URL_PATTERN, label="微信"
        )
        for result in fallback:
            items.append({
                "title": result.title,
                "snippet": result.snippet,
                "url": result.url,
                "source_name": "",
                "wechat_id": "",
                "date": result.date,
                "date_confidence": "med" if result.date else "low",
                "engagement": {},
                "source": f"site-search:{result.engine}",
            })
        if fallback:
            sys.stderr.write(f"[微信] 搜狗不可用，已用公开搜索兜底获取 {len(fallback)} 条公众号文章链接。\n")

    if not items and errors:
        raise http.HTTPError("微信公众号搜索失败：" + errors[0] + "；" + websearch.describe_failure("微信"))

    scored = []
    for item in items:
        title = item.get("title", "")
        snippet = item.get("snippet", "")
        rel = relevance.token_overlap_relevance(topic, f"{title} {snippet}")
        item["relevance"] = rel
        account = item.get("source_name") or "公众号"
        item["why_relevant"] = f"微信公众号（{account}）：{title[:50]}"
        scored.append(item)

    scored.sort(key=lambda x: x.get("relevance", 0), reverse=True)
    scored = scored[:limit]
    for i, item in enumerate(scored):
        item["id"] = f"WX{i+1}"
    return scored


def _search_via_api(topic: str, limit: int, api_key: str) -> List[Dict[str, Any]]:
    """通过第三方 API（极速数据）搜索微信公众号文章。"""
    items = []
    try:
        encoded = urllib.parse.quote(topic)
        url = f"https://api.jisuapi.com/weixin/search?keyword={encoded}&pagenum=1&pagesize={limit}&appkey={api_key}"
        data = http.get(url, headers=http.browser_headers(accept="json"), timeout=15, retries=1)
        if str(data.get("status")) == "0":
            for article in (data.get("result") or {}).get("list", []):
                items.append({
                    "title": article.get("name", ""),
                    "snippet": article.get("description", ""),
                    "url": article.get("url", ""),
                    "source_name": article.get("weixinname", ""),
                    "wechat_id": article.get("weixinhao", ""),
                    "date": article.get("date"),
                    "engagement": {},
                    "source": "api",
                })
    except Exception as e:
        sys.stderr.write(f"[微信] API 搜索失败: {e}\n")
    return items


def _search_via_sogou(topic: str, page: int = 1) -> List[Dict[str, Any]]:
    """通过搜狗微信搜索（单页）。"""
    params = {"type": "2", "ie": "utf8", "query": topic}
    if page > 1:
        params["page"] = str(page)
    url = f"{SOGOU_BASE}/weixin?{urllib.parse.urlencode(params)}"
    _status, final_url, body = http.fetch(
        url, headers=http.browser_headers(referer=f"{SOGOU_BASE}/"), timeout=15
    )
    if "antispider" in final_url or ("antispider" in body and "news-list" not in body):
        raise http.HTTPError("搜狗微信触发反爬验证（antispider），请稍后再试或配置 WECHAT_API_KEY")
    return parse_sogou_html(body)


def parse_sogou_html(body: str) -> List[Dict[str, Any]]:
    """Parse ``ul.news-list`` result cards from a Sogou WeChat SERP."""
    items: List[Dict[str, Any]] = []
    list_start = body.find('class="news-list"')
    if list_start < 0:
        return items
    segment = body[list_start:]
    end = segment.find("</ul>")
    if end > 0:
        segment = segment[:end]

    for block in re.findall(r"<li[^>]*>([\s\S]*?)</li>", segment):
        title_match = re.search(r'<h3>\s*<a[^>]*href="([^"]+)"[^>]*>([\s\S]*?)</a>', block)
        if not title_match:
            continue
        href = html_lib.unescape(title_match.group(1))
        if href.startswith("/"):
            href = SOGOU_BASE + href
        title = _clean(title_match.group(2))
        if not title:
            continue
        snippet_match = re.search(r'<p class="txt-info"[^>]*>([\s\S]*?)</p>', block)
        account_match = re.search(r'<span class="all-time-y2">([\s\S]*?)</span>', block) or re.search(
            r'<a[^>]*class="account"[^>]*>([\s\S]*?)</a>', block
        )
        ts_match = re.search(r"timeConvert\('(\d+)'\)", block)
        date_str = dates.timestamp_to_date(int(ts_match.group(1))) if ts_match else None
        items.append({
            "title": title,
            "snippet": _clean(snippet_match.group(1)) if snippet_match else "",
            "url": href,
            "source_name": _clean(account_match.group(1)) if account_match else "",
            "wechat_id": "",
            "date": date_str,
            "engagement": {},
            "source": "sogou",
        })
    return items


def _clean(text: str) -> str:
    text = re.sub(r"<!--.*?-->", "", text or "", flags=re.S)
    text = re.sub(r"<[^>]+>", "", text)
    text = html_lib.unescape(text)
    return re.sub(r"\s+", " ", text).strip()
