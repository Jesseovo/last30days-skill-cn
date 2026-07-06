"""MediaCrawler 爬虫桥接模块 — 基于 Playwright 浏览器自动化的数据采集。

灵感来源: https://github.com/NanmiCoder/MediaCrawler
技术原理: 利用 Playwright 控制浏览器，通过保留登录态的上下文获取平台数据，
         无需逆向复杂加密算法，无需付费 API Key。

v2.1 改动：
- 抽取 `_launch_browser_context` 公共函数，统一 locale/viewport/UA
- 小红书/抖音改用 `page.on("response")` XHR 拦截，避开 Virtual DOM 渲染
- `page.goto` 统一使用 `wait_until="domcontentloaded"`，配合条件轮询替代固定 sleep

⚠️ 免责声明:
本模块仅供学习和研究目的。使用者必须遵守相关法律法规及各平台的服务条款。
禁止用于商业用途、大规模数据采集或任何非法活动。

Author: Jesse (https://github.com/Jesseovo)
"""

import json
import os
import re
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

from . import dates

COOKIE_DIR = Path.home() / ".config" / "last30days-cn" / "browser_cookies"
_playwright_available: Optional[bool] = None

_DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)


def is_playwright_available() -> bool:
    """检查 Playwright 是否已安装并可用。"""
    global _playwright_available
    if _playwright_available is not None:
        return _playwright_available
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
        _playwright_available = True
    except ImportError:
        _playwright_available = False
    return _playwright_available


def _ensure_cookie_dir():
    COOKIE_DIR.mkdir(parents=True, exist_ok=True)


def _get_cookie_path(platform: str) -> Path:
    _ensure_cookie_dir()
    return COOKIE_DIR / f"{platform}_cookies.json"


def save_cookies(platform: str, cookies: list):
    path = _get_cookie_path(platform)
    path.write_text(json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8")


def load_cookies(platform: str) -> Optional[list]:
    path = _get_cookie_path(platform)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def _clean_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", str(text))
    return re.sub(r"\s+", " ", text).strip()


@contextmanager
def _launch_browser_context(platform: str, mobile: bool = False, headless: bool = True):
    """统一构造 Playwright 浏览器上下文，自动加载并回写 cookies。

    Yields:
        (browser, context, page) 三元组
    """
    from playwright.sync_api import sync_playwright

    ua = _MOBILE_UA if mobile else _DESKTOP_UA
    viewport = {"width": 390, "height": 844} if mobile else {"width": 1280, "height": 800}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        try:
            context = browser.new_context(
                user_agent=ua,
                locale="zh-CN",
                timezone_id="Asia/Shanghai",
                viewport=viewport,
            )
            cookies = load_cookies(platform)
            if cookies:
                try:
                    context.add_cookies(cookies)
                except Exception as e:
                    sys.stderr.write(f"[爬虫-{platform}] 加载 Cookie 失败: {e}\n")

            page = context.new_page()
            try:
                yield browser, context, page
            finally:
                try:
                    save_cookies(platform, context.cookies())
                except Exception:
                    pass
        finally:
            try:
                browser.close()
            except Exception:
                pass


def _wait_for(page, predicate, timeout_ms: int = 8000, interval_ms: int = 500) -> bool:
    """轮询等待条件满足，返回是否在超时前命中。"""
    elapsed = 0
    while elapsed < timeout_ms:
        try:
            if predicate():
                return True
        except Exception:
            pass
        page.wait_for_timeout(interval_ms)
        elapsed += interval_ms
    return False


def crawl_weibo(topic: str, limit: int = 20) -> List[Dict[str, Any]]:
    """通过浏览器自动化爬取微博搜索结果。"""
    if not is_playwright_available():
        return []

    items: List[Dict[str, Any]] = []
    try:
        with _launch_browser_context("weibo", mobile=True) as (browser, context, page):
            search_url = (
                f"https://m.weibo.cn/api/container/getIndex?"
                f"containerid=100103type%3D1%26q%3D{topic}&page_type=searchall"
            )
            page.goto(
                f"https://m.weibo.cn/search?containerid=100103type%3D1%26q%3D{topic}",
                wait_until="domcontentloaded",
                timeout=20000,
            )
            page.wait_for_timeout(1500)

            response = page.evaluate(
                """
                async (url) => {
                    const resp = await fetch(url);
                    return await resp.json();
                }
                """,
                search_url,
            )

            if isinstance(response, dict):
                cards = response.get("data", {}).get("cards", [])
                for card in cards[:limit]:
                    if card.get("card_type") == 9:
                        mblog = card.get("mblog", {})
                        if mblog:
                            items.append(_parse_weibo_mblog(mblog))
                    elif card.get("card_type") == 11:
                        for group in card.get("card_group", []):
                            mblog = group.get("mblog", {})
                            if mblog:
                                items.append(_parse_weibo_mblog(mblog))
    except Exception as e:
        sys.stderr.write(f"[爬虫-微博] 浏览器爬取失败: {e}\n")
    return items


def _parse_weibo_mblog(mblog: dict) -> Dict[str, Any]:
    text = _clean_html(mblog.get("text", ""))
    user = mblog.get("user", {})
    mid = mblog.get("mid", "") or mblog.get("id", "")

    return {
        "text": text,
        "url": f"https://weibo.com/{user.get('id', '')}/{mid}",
        "author_handle": user.get("screen_name", ""),
        "author_id": str(user.get("id", "")),
        "date": _parse_relative_date(mblog.get("created_at", "")),
        "engagement": {
            "reposts": mblog.get("reposts_count", 0),
            "comments": mblog.get("comments_count", 0),
            "likes": mblog.get("attitudes_count", 0),
        },
        "source": "crawler",
    }


def crawl_xiaohongshu(topic: str, limit: int = 20) -> List[Dict[str, Any]]:
    """通过浏览器自动化爬取小红书搜索结果。

    v2.1：参考 MediaCrawler 思路，优先拦截 XHR `/api/sns/web/v1/search/notes`
    避开 Virtual DOM。失败时回退到 DOM 选择器（命中率较低，仅作兜底）。
    """
    if not is_playwright_available():
        return []

    items: List[Dict[str, Any]] = []
    try:
        with _launch_browser_context("xiaohongshu") as (browser, context, page):
            captured: Dict[str, Any] = {"payload": None}

            def _on_response(resp):
                try:
                    url = resp.url
                    if "/api/sns/web/v1/search/notes" in url and resp.status == 200:
                        captured["payload"] = resp.json()
                except Exception:
                    pass

            page.on("response", _on_response)

            search_url = (
                f"https://www.xiaohongshu.com/search_result?"
                f"keyword={topic}&source=web_search_result_notes"
            )
            try:
                page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            except Exception as e:
                sys.stderr.write(f"[爬虫-小红书] 页面加载失败: {e}\n")

            for _ in range(5):
                if captured["payload"]:
                    break
                try:
                    page.mouse.wheel(0, 2000)
                except Exception:
                    pass
                page.wait_for_timeout(1500)

            payload = captured["payload"]
            if isinstance(payload, dict):
                data = payload.get("data") or {}
                raw_items = data.get("items") or []
                for raw in raw_items[:limit]:
                    note_card = raw.get("note_card") or {}
                    if not note_card:
                        continue
                    note_id = raw.get("id") or note_card.get("note_id", "")
                    user = note_card.get("user") or {}
                    interact = note_card.get("interact_info") or {}
                    items.append({
                        "title": note_card.get("display_title") or note_card.get("title", ""),
                        "desc": note_card.get("desc", ""),
                        "url": f"https://www.xiaohongshu.com/explore/{note_id}" if note_id else "",
                        "author_name": user.get("nickname") or user.get("nick_name", ""),
                        "author_id": user.get("user_id") or user.get("userid", ""),
                        "date": None,
                        "engagement": {
                            "likes": _parse_count(str(interact.get("liked_count", "0"))),
                            "collects": _parse_count(str(interact.get("collected_count", "0"))),
                            "comments": _parse_count(str(interact.get("comment_count", "0"))),
                            "shares": _parse_count(str(interact.get("share_count", "0"))),
                        },
                        "hashtags": [],
                        "images": [
                            img.get("url_default") or img.get("url", "")
                            for img in (note_card.get("image_list") or [])
                            if isinstance(img, dict)
                        ],
                        "source": "crawler-xhr",
                    })
            elif not payload:
                sys.stderr.write(
                    "[爬虫-小红书] 未捕获搜索 XHR，可能需要重新登录、验证码通过，或平台接口已调整；"
                    "将继续尝试 DOM/站内搜索兜底。\n"
                )

            if not items:
                note_elements = page.query_selector_all(
                    "section.note-item, div[class*='note-item'], a[class*='cover'], a[href*='/explore/']"
                )
                for elem in note_elements[:limit]:
                    try:
                        title_el = elem.query_selector("span[class*='title'], div[class*='title']")
                        title = title_el.inner_text() if title_el else ""
                        link = elem.get_attribute("href") or ""
                        if link and not link.startswith("http"):
                            link = f"https://www.xiaohongshu.com{link}"

                        author_el = elem.query_selector("span[class*='name'], div[class*='author']")
                        author = author_el.inner_text() if author_el else ""

                        likes_el = elem.query_selector("span[class*='like'], span[class*='count']")
                        likes_text = likes_el.inner_text() if likes_el else "0"
                        likes = _parse_count(likes_text)

                        items.append({
                            "title": title,
                            "desc": "",
                            "url": link,
                            "author_name": author,
                            "author_id": "",
                            "date": None,
                            "engagement": {
                                "likes": likes,
                                "collects": 0,
                                "comments": 0,
                                "shares": 0,
                            },
                            "hashtags": [],
                            "images": [],
                            "source": "crawler-dom",
                        })
                    except Exception:
                        continue
            if not items:
                sys.stderr.write(
                    "[爬虫-小红书] Playwright 未解析到结果；这通常是登录态失效、反爬验证或页面结构变更导致。\n"
                )
    except Exception as e:
        sys.stderr.write(f"[爬虫-小红书] 浏览器爬取失败: {e}\n")
    return items


def crawl_douyin(topic: str, limit: int = 20) -> List[Dict[str, Any]]:
    """通过浏览器自动化爬取抖音搜索结果。

    v2.1：优先拦截 XHR `/aweme/v1/web/search/item/`，DOM 解析作为兜底。
    """
    if not is_playwright_available():
        return []

    items: List[Dict[str, Any]] = []
    try:
        with _launch_browser_context("douyin") as (browser, context, page):
            captured: Dict[str, Any] = {"payload": None}

            def _on_response(resp):
                try:
                    url = resp.url
                    if "/aweme/v1/web/search/item" in url and resp.status == 200:
                        data = resp.json()
                        if isinstance(data, dict) and data.get("data"):
                            captured["payload"] = data
                except Exception:
                    pass

            page.on("response", _on_response)

            search_url = f"https://www.douyin.com/search/{topic}?type=video"
            try:
                page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            except Exception as e:
                sys.stderr.write(f"[爬虫-抖音] 页面加载失败: {e}\n")

            for _ in range(5):
                if captured["payload"]:
                    break
                try:
                    page.mouse.wheel(0, 2000)
                except Exception:
                    pass
                page.wait_for_timeout(1500)

            payload = captured["payload"]
            if isinstance(payload, dict):
                for entry in (payload.get("data") or [])[:limit]:
                    aweme = entry.get("aweme_info") or entry
                    if not isinstance(aweme, dict):
                        continue
                    aweme_id = aweme.get("aweme_id", "")
                    author = aweme.get("author") or {}
                    stats = aweme.get("statistics") or {}
                    items.append({
                        "text": aweme.get("desc", ""),
                        "url": f"https://www.douyin.com/video/{aweme_id}" if aweme_id else "",
                        "author_name": author.get("nickname", ""),
                        "author_id": author.get("uid", ""),
                        "date": None,
                        "engagement": {
                            "views": stats.get("play_count", 0),
                            "likes": stats.get("digg_count", 0),
                            "comments": stats.get("comment_count", 0),
                            "shares": stats.get("share_count", 0),
                        },
                        "hashtags": [],
                        "duration": (aweme.get("duration") or 0) // 1000,
                        "source": "crawler-xhr",
                    })

            if not items:
                video_elements = page.query_selector_all(
                    "div[class*='video-card'], li[class*='search-result']"
                )
                for elem in video_elements[:limit]:
                    try:
                        title_el = elem.query_selector(
                            "a[class*='title'], span[class*='title'], p[class*='desc']"
                        )
                        title = title_el.inner_text() if title_el else ""

                        link_el = elem.query_selector("a[href*='/video/']")
                        link = ""
                        if link_el:
                            href = link_el.get_attribute("href") or ""
                            if href.startswith("/"):
                                link = f"https://www.douyin.com{href}"
                            else:
                                link = href

                        author_el = elem.query_selector(
                            "span[class*='author'], span[class*='nickname']"
                        )
                        author = author_el.inner_text() if author_el else ""

                        likes_el = elem.query_selector("span[class*='like'], span[class*='digg']")
                        likes = _parse_count(likes_el.inner_text() if likes_el else "0")

                        items.append({
                            "text": title,
                            "url": link,
                            "author_name": author,
                            "author_id": "",
                            "date": None,
                            "engagement": {
                                "views": 0,
                                "likes": likes,
                                "comments": 0,
                                "shares": 0,
                            },
                            "hashtags": [],
                            "duration": 0,
                            "source": "crawler-dom",
                        })
                    except Exception:
                        continue
    except Exception as e:
        sys.stderr.write(f"[爬虫-抖音] 浏览器爬取失败: {e}\n")
    return items


def crawl_bilibili(topic: str, limit: int = 20) -> List[Dict[str, Any]]:
    """通过浏览器自动化爬取B站搜索结果。"""
    if not is_playwright_available():
        return []

    items: List[Dict[str, Any]] = []
    try:
        with _launch_browser_context("bilibili") as (browser, context, page):
            search_url = f"https://search.bilibili.com/all?keyword={topic}&order=totalrank"
            try:
                page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            except Exception as e:
                sys.stderr.write(f"[爬虫-B站] 页面加载失败: {e}\n")

            _wait_for(
                page,
                lambda: bool(page.query_selector("div.bili-video-card, div[class*='video-list-item']")),
                timeout_ms=8000,
            )

            video_elements = page.query_selector_all(
                "div.bili-video-card, div[class*='video-list-item']"
            )
            for elem in video_elements[:limit]:
                try:
                    title_el = elem.query_selector("h3[class*='title'], a[class*='title']")
                    title = _clean_html(title_el.inner_text()) if title_el else ""

                    link_el = elem.query_selector("a[href*='/video/']")
                    link = ""
                    if link_el:
                        href = link_el.get_attribute("href") or ""
                        if href.startswith("//"):
                            link = f"https:{href}"
                        elif href.startswith("/"):
                            link = f"https://www.bilibili.com{href}"
                        else:
                            link = href

                    author_el = elem.query_selector(
                        "span[class*='name'], span.bili-video-card__info--author"
                    )
                    author = author_el.inner_text() if author_el else ""

                    views_el = elem.query_selector("span[class*='play'], span[class*='view']")
                    views = _parse_count(views_el.inner_text() if views_el else "0")

                    items.append({
                        "title": title,
                        "url": link,
                        "bvid": "",
                        "channel_name": author,
                        "author_mid": "",
                        "date": None,
                        "duration": "",
                        "description": "",
                        "engagement": {
                            "views": views,
                            "danmaku": 0,
                            "comments": 0,
                            "favorites": 0,
                            "likes": 0,
                        },
                        "source": "crawler",
                    })
                except Exception:
                    continue
    except Exception as e:
        sys.stderr.write(f"[爬虫-B站] 浏览器爬取失败: {e}\n")
    return items


def crawl_zhihu(topic: str, limit: int = 20) -> List[Dict[str, Any]]:
    """通过浏览器自动化爬取知乎搜索结果。"""
    if not is_playwright_available():
        return []

    items: List[Dict[str, Any]] = []
    try:
        with _launch_browser_context("zhihu") as (browser, context, page):
            search_url = f"https://www.zhihu.com/search?type=content&q={topic}"
            try:
                page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            except Exception as e:
                sys.stderr.write(f"[爬虫-知乎] 页面加载失败: {e}\n")

            _wait_for(
                page,
                lambda: bool(page.query_selector("div.SearchResult-Card, div[class*='List-item']")),
                timeout_ms=8000,
            )

            result_elements = page.query_selector_all(
                "div.SearchResult-Card, div[class*='List-item']"
            )
            for elem in result_elements[:limit]:
                try:
                    title_el = elem.query_selector(
                        "h2[class*='ContentItem-title'], span[class*='Highlight']"
                    )
                    title = _clean_html(title_el.inner_text()) if title_el else ""

                    link_el = elem.query_selector("a[href*='/question/'], a[href*='/p/']")
                    link = ""
                    if link_el:
                        href = link_el.get_attribute("href") or ""
                        if href.startswith("/"):
                            link = f"https://www.zhihu.com{href}"
                        else:
                            link = href

                    excerpt_el = elem.query_selector(
                        "span[class*='RichText'], div[class*='RichText']"
                    )
                    excerpt = _clean_html(excerpt_el.inner_text()[:300]) if excerpt_el else ""

                    author_el = elem.query_selector(
                        "span[class*='AuthorInfo'] a, a[class*='UserLink']"
                    )
                    author = author_el.inner_text() if author_el else ""

                    voteup_el = elem.query_selector(
                        "button[class*='VoteButton'] span, span[class*='vote']"
                    )
                    voteups = _parse_count(voteup_el.inner_text() if voteup_el else "0")

                    items.append({
                        "title": title,
                        "excerpt": excerpt,
                        "url": link,
                        "author": author,
                        "date": None,
                        "content_type": "search_result",
                        "engagement": {
                            "voteups": voteups,
                            "comments": 0,
                            "collects": 0,
                        },
                        "source": "crawler",
                    })
                except Exception:
                    continue
            if not items:
                sys.stderr.write(
                    "[爬虫-知乎] Playwright 未解析到结果；这通常是登录态失效、反爬验证或页面结构变更导致。\n"
                )
    except Exception as e:
        sys.stderr.write(f"[爬虫-知乎] 浏览器爬取失败: {e}\n")
    return items


def _parse_count(text: str) -> int:
    """解析数量文本，支持 '1.2万' / '1.2w' / '12k' 等格式。"""
    if not text:
        return 0
    text = str(text).strip().replace(",", "")
    try:
        if "万" in text or text.lower().endswith("w"):
            num = float(re.sub(r"[万wW]", "", text))
            return int(num * 10000)
        elif "亿" in text:
            num = float(text.replace("亿", ""))
            return int(num * 100000000)
        elif text.lower().endswith("k"):
            num = float(text[:-1])
            return int(num * 1000)
        return int(float(re.sub(r"[^\d.]", "", text or "0")))
    except (ValueError, TypeError):
        return 0


def _parse_relative_date(date_str: str) -> Optional[str]:
    """解析微博的相对时间格式。"""
    if not date_str:
        return None

    from datetime import timedelta
    now = datetime.now(dates.CST)

    try:
        dt = datetime.strptime(date_str, "%a %b %d %H:%M:%S %z %Y")
        return dt.astimezone(dates.CST).strftime("%Y-%m-%d")
    except ValueError:
        pass

    if "分钟前" in date_str:
        m = re.search(r"(\d+)", date_str)
        if m:
            return (now - timedelta(minutes=int(m.group(1)))).strftime("%Y-%m-%d")
    if "小时前" in date_str:
        m = re.search(r"(\d+)", date_str)
        if m:
            return (now - timedelta(hours=int(m.group(1)))).strftime("%Y-%m-%d")
    if "昨天" in date_str:
        return (now - timedelta(days=1)).strftime("%Y-%m-%d")

    m = re.match(r"(\d{2})-(\d{2})", date_str)
    if m:
        return f"{now.year}-{m.group(1)}-{m.group(2)}"
    return None


def get_crawler_status() -> Dict[str, Any]:
    """获取爬虫引擎的状态信息。"""
    pw_available = is_playwright_available()
    cached_platforms = []

    if COOKIE_DIR.exists():
        for f in COOKIE_DIR.glob("*_cookies.json"):
            platform = f.stem.replace("_cookies", "")
            cached_platforms.append(platform)

    return {
        "playwright_available": pw_available,
        "cached_logins": cached_platforms,
        "cookie_dir": str(COOKIE_DIR),
    }
