"""B站搜索模块 - 搜索哔哩哔哩视频内容。

Author: Jesse (https://github.com/Jesseovo)

v4 数据路径（按顺序自动降级）：
1. WBI 签名搜索 ``/x/web-interface/wbi/search/type``，带 ``buvid3``/``buvid4``
   访客 Cookie 和完整浏览器 UA（issue #17：B站 WAF 会对不完整 UA 直接回 412），
   并用 ``pubtime_begin_s``/``pubtime_end_s`` 把结果限定在研究时间窗内。
2. 旧版 ``/x/web-interface/search/type``（WBI 失败或被风控时）。
3. Playwright 浏览器爬虫（可选）。

可选 ``BILIBILI_COOKIE``（浏览器复制的 ``SESSDATA=...; buvid3=...``）可降低风控概率。
"""

import hashlib
import re
import sys
import threading
import time
import urllib.parse
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from . import dates, http, relevance

SEARCH_REFERER = "https://search.bilibili.com/"
WBI_SEARCH_URL = "https://api.bilibili.com/x/web-interface/wbi/search/type"
LEGACY_SEARCH_URL = "https://api.bilibili.com/x/web-interface/search/type"
SPI_URL = "https://api.bilibili.com/x/frontend/finger/spi"
NAV_URL = "https://api.bilibili.com/x/web-interface/nav"
HOTWORD_URL = "https://s.search.bilibili.com/main/hotword"

# Risk-control answers: HTTP 412 or JSON code -412 / -352.
RISK_CODES = {-412, -352}

MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
    33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
    61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
    36, 20, 34, 44, 52,
]

_wbi_cache: Dict[str, Any] = {"keys": None, "at": 0.0}
_wbi_lock = threading.Lock()
_WBI_TTL_SECONDS = 6 * 3600


class BilibiliRiskControl(Exception):
    """Bilibili answered with 412 / -412 / -352."""


def get_mixin_key(orig: str) -> str:
    """Scramble img_key + sub_key into the 32-char WBI mixin key."""
    return "".join(orig[i] for i in MIXIN_KEY_ENC_TAB)[:32]


def sign_wbi(params: Dict[str, Any], img_key: str, sub_key: str, wts: Optional[int] = None) -> Dict[str, Any]:
    """Return ``params`` plus ``wts`` and ``w_rid`` (Bilibili WBI signature)."""
    mixin_key = get_mixin_key(img_key + sub_key)
    signed = dict(params)
    signed["wts"] = int(wts if wts is not None else round(time.time()))
    signed = dict(sorted(signed.items()))
    signed = {k: "".join(ch for ch in str(v) if ch not in "!'()*") for k, v in signed.items()}
    query = urllib.parse.urlencode(signed)
    signed["w_rid"] = hashlib.md5((query + mixin_key).encode("utf-8")).hexdigest()
    return signed


def _key_from_url(url: str) -> str:
    return url.rsplit("/", 1)[-1].split(".", 1)[0]


def _new_session(cookie: Optional[str] = None) -> http.Session:
    session = http.Session(http.browser_headers(referer=SEARCH_REFERER, accept="json"))
    if cookie:
        session.load_cookie_header(cookie, ".bilibili.com")
    if not session.get_cookie("buvid3"):
        _attach_buvid(session)
    return session


def _attach_buvid(session: http.Session) -> None:
    """Fetch anonymous buvid3/buvid4 (required by the search WAF)."""
    try:
        data = session.get_json(SPI_URL, timeout=8)
        payload = (data or {}).get("data") or {}
        if payload.get("b_3"):
            session.set_cookie("buvid3", payload["b_3"], ".bilibili.com")
        if payload.get("b_4"):
            session.set_cookie("buvid4", payload["b_4"], ".bilibili.com")
        session.set_cookie("b_nut", str(int(time.time())), ".bilibili.com")
    except Exception as exc:
        http.log(f"[B站] 获取 buvid 失败: {exc}")


def _wbi_keys(session: http.Session) -> Tuple[str, str]:
    with _wbi_lock:
        cached = _wbi_cache.get("keys")
        if cached and time.time() - _wbi_cache.get("at", 0) < _WBI_TTL_SECONDS:
            return cached
    data = session.get_json(NAV_URL, timeout=8)
    wbi = ((data or {}).get("data") or {}).get("wbi_img") or {}
    img_url, sub_url = wbi.get("img_url"), wbi.get("sub_url")
    if not img_url or not sub_url:
        raise BilibiliRiskControl("nav 接口未返回 WBI 密钥")
    keys = (_key_from_url(img_url), _key_from_url(sub_url))
    with _wbi_lock:
        _wbi_cache["keys"] = keys
        _wbi_cache["at"] = time.time()
    return keys


def _date_window(from_date: str, to_date: str) -> Tuple[int, int]:
    start = datetime.strptime(from_date, "%Y-%m-%d").replace(tzinfo=dates.CST)
    end = datetime.strptime(to_date, "%Y-%m-%d").replace(tzinfo=dates.CST)
    return int(start.timestamp()), int(end.timestamp()) + 86399


def _check_payload(data: Any) -> List[Dict[str, Any]]:
    if not isinstance(data, dict):
        raise BilibiliRiskControl("返回内容不是 JSON 对象")
    code = data.get("code")
    if code in RISK_CODES:
        raise BilibiliRiskControl(f"code {code}: {data.get('message', '')}")
    if code not in (0, None):
        raise http.HTTPError(f"B站接口返回 code {code}: {data.get('message', '')}")
    return list(((data.get("data") or {}).get("result")) or [])


def _search_once(
    session: http.Session,
    topic: str,
    page: int,
    order: str,
    window: Optional[Tuple[int, int]],
    use_wbi: bool,
) -> List[Dict[str, Any]]:
    params: Dict[str, Any] = {
        "search_type": "video",
        "keyword": topic,
        "page": page,
        "page_size": 20,
        "order": order,
    }
    if window:
        params["pubtime_begin_s"], params["pubtime_end_s"] = window
    try:
        if use_wbi:
            img_key, sub_key = _wbi_keys(session)
            url = f"{WBI_SEARCH_URL}?{urllib.parse.urlencode(sign_wbi(params, img_key, sub_key))}"
        else:
            url = f"{LEGACY_SEARCH_URL}?{urllib.parse.urlencode(params)}"
        data = session.get_json(url, timeout=15)
    except http.HTTPError as exc:
        if exc.status_code == 412:
            raise BilibiliRiskControl("HTTP 412") from exc
        raise
    path = "wbi-search" if use_wbi else "legacy-search"
    items = [_parse_video(v) for v in _check_payload(data)]
    for item in items:
        item["source"] = path
    return items


def search_bilibili(
    topic: str,
    from_date: str,
    to_date: str,
    depth: str = "default",
    cookie: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """搜索B站视频。

    Args:
        topic: 搜索关键词
        from_date: 起始日期 YYYY-MM-DD
        to_date: 结束日期 YYYY-MM-DD
        depth: 搜索深度 quick/default/deep
        cookie: 可选 BILIBILI_COOKIE

    Returns:
        B站视频列表
    """
    limit_map = {"quick": 10, "default": 20, "deep": 40}
    limit = limit_map.get(depth, 20)
    plan = {
        "quick": [("totalrank", 1)],
        "default": [("totalrank", 1), ("click", 1)],
        "deep": [("totalrank", 1), ("totalrank", 2), ("click", 1), ("pubdate", 1)],
    }.get(depth, [("totalrank", 1), ("click", 1)])

    try:
        window: Optional[Tuple[int, int]] = _date_window(from_date, to_date)
    except (TypeError, ValueError):
        window = None

    items: List[Dict[str, Any]] = []
    errors: List[str] = []
    session = _new_session(cookie)
    use_wbi = True
    for order, page in plan:
        try:
            items.extend(_search_once(session, topic, page, order, window, use_wbi))
        except BilibiliRiskControl as exc:
            errors.append(f"{order}#{page}: 风控拦截 ({exc})")
            sys.stderr.write(f"[B站] 搜索被风控拦截（{exc}），刷新 buvid 后改用旧版接口重试...\n")
            session = _new_session(cookie)
            use_wbi = False
            try:
                items.extend(_search_once(session, topic, page, order, window, use_wbi))
            except Exception as retry_exc:
                errors.append(f"legacy: {retry_exc}")
                break
        except Exception as exc:
            errors.append(f"{order}#{page}: {exc}")
            sys.stderr.write(f"[B站] 搜索失败（{order} 第 {page} 页）: {exc}\n")
            break

    items = _dedupe_by_bvid(items)

    if not items:
        try:
            from . import crawler_bridge
            if crawler_bridge.is_playwright_available():
                sys.stderr.write("[B站] 公开 API 无结果或被拦截，尝试浏览器爬虫...\n")
                items = crawler_bridge.crawl_bilibili(topic, limit)
                if items:
                    sys.stderr.write(f"[B站] 爬虫模式获取 {len(items)} 条结果\n")
                else:
                    sys.stderr.write("[B站] 爬虫模式未返回结果\n")
            elif errors:
                sys.stderr.write("[B站] 公开 API 失败，且 Playwright 不可用，无法回退浏览器爬虫\n")
        except Exception as e:
            sys.stderr.write(f"[B站] 爬虫模式失败: {e}\n")

    if not items and errors:
        raise http.HTTPError("B站搜索失败：" + "；".join(errors[:3]))

    scored = []
    for item in items:
        title = _clean_html(item.get("title", ""))
        tags = item.get("tags") or []
        rel = relevance.token_overlap_relevance(topic, f"{title} {item.get('description', '')}", hashtags=tags)
        item["title"] = title
        item["relevance"] = rel
        item["why_relevant"] = f"B站视频：{title[:50]}"
        scored.append(item)

    scored.sort(key=lambda x: x.get("relevance", 0), reverse=True)
    scored = scored[:limit]
    for i, item in enumerate(scored):
        item["id"] = f"BL{i+1}"
    return scored


def _dedupe_by_bvid(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out = []
    for item in items:
        key = item.get("bvid") or item.get("url")
        if key and key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _search_page(topic: str, page: int = 1) -> List[Dict[str, Any]]:
    """兼容旧调用：搜索单页（不带时间窗）。"""
    session = _new_session()
    try:
        return _search_once(session, topic, page, "totalrank", None, True)
    except BilibiliRiskControl:
        return _search_once(_new_session(), topic, page, "totalrank", None, False)


def _duration_seconds(value: Any) -> Optional[int]:
    if isinstance(value, (int, float)):
        return int(value)
    if not value:
        return None
    parts = str(value).split(":")
    try:
        total = 0
        for part in parts:
            total = total * 60 + int(part)
        return total
    except ValueError:
        return None


def _to_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _parse_video(v: dict) -> Dict[str, Any]:
    """解析B站视频搜索结果。"""
    bvid = v.get("bvid", "")
    pubdate = v.get("pubdate", 0)
    date_str = dates.timestamp_to_date(pubdate) if pubdate else None
    tags = [t for t in str(v.get("tag") or "").split(",") if t]
    return {
        "title": v.get("title", ""),
        "url": f"https://www.bilibili.com/video/{bvid}" if bvid else v.get("arcurl", ""),
        "bvid": bvid,
        "channel_name": v.get("author", ""),
        "author_mid": str(v.get("mid", "") or ""),
        "date": date_str,
        "duration": _duration_seconds(v.get("duration")),
        "description": _clean_html(v.get("description", "")),
        "tags": tags[:10],
        "engagement": {
            "views": _to_int(v.get("play")),
            "danmaku": _to_int(v.get("video_review") or v.get("danmaku")),
            "comments": _to_int(v.get("review") or v.get("comment")),
            "favorites": _to_int(v.get("favorites")),
            "likes": _to_int(v.get("like")),
        },
    }


def _clean_html(text: str) -> str:
    """清除搜索结果中的 HTML 高亮标签。"""
    text = re.sub(r"<[^>]+>", "", text or "")
    return text.replace("&amp;", "&").replace("&quot;", '"').strip()


def fetch_hot(limit: int = 30) -> List[Dict[str, Any]]:
    """B站热搜词（热榜模式使用）。"""
    session = _new_session()
    data = session.get_json(f"{HOTWORD_URL}?limit={max(10, limit)}", timeout=10)
    out = []
    for idx, entry in enumerate((data or {}).get("list") or [], start=1):
        word = entry.get("keyword") or ""
        title = entry.get("show_name") or word
        if not title:
            continue
        out.append({
            "rank": entry.get("pos") or idx,
            "title": title,
            "url": f"https://search.bilibili.com/all?keyword={urllib.parse.quote(word or title)}",
            "hot_value": entry.get("heat_score") or entry.get("score") or None,
            "label": (entry.get("word_type") == 7 and "直播") or "",
        })
        if len(out) >= limit:
            break
    return out
