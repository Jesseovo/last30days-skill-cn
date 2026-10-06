"""Playwright 浏览器桥接模块 — 登录态复用 + XHR/页面状态解析。

灵感来源: https://github.com/NanmiCoder/MediaCrawler
技术原理: 用 Playwright 驱动真实浏览器，复用用户自己登录后的会话，由页面自己
发出（并签名）搜索请求，我们只拦截响应 / 读取页面状态，不逆向任何加密算法。

v4 改动：
- 新增 ``login <platform>``：弹出可见浏览器让用户扫码/登录一次，保存登录态。
  v3 只会在匿名的无头会话结束时回写 Cookie，用户根本没有登录入口，所以
  小红书/微博/知乎/抖音的浏览器模式基本只能拿到登录墙（issue #8 / #11）。
- 也可用 ``login <platform> --cookie "<浏览器复制的 Cookie>"`` 在无图形界面的
  机器上导入登录态。
- 浏览器启动失败会触发熔断：本次运行内其它平台立即跳过浏览器路径，并给出
  旧电脑（issue #13）的修复建议，而不是每个平台各自卡住几十秒。
- 并发浏览器数量受 ``LAST30DAYS_BROWSER_CONCURRENCY``（默认 2）限制。
- UA 与实际浏览器版本一致；小红书新增 ``window.__INITIAL_STATE__`` 解析；
  知乎/抖音/B站改为拦截页面自己的搜索 XHR；抖音结果带上发布日期。

⚠️ 免责声明:
本模块仅供学习和研究目的。使用者必须遵守相关法律法规及各平台的服务条款。
禁止用于商业用途、大规模数据采集或任何非法活动。

Author: Jesse (https://github.com/Jesseovo)
"""

import json
import os
import platform as platform_mod
import re
import sys
import tempfile
import threading
import time
import urllib.parse
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import dates


def _config_dir() -> Path:
    override = os.environ.get("LAST30DAYS_CN_CONFIG_DIR") or os.environ.get("LAST30DAYS_CONFIG_DIR")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".config" / "last30days-cn"


COOKIE_DIR = _config_dir() / "browser_cookies"
_playwright_available: Optional[bool] = None
_BROWSER_PATH_ENV = "LAST30DAYS_BROWSER_PATH"
_BROWSER_CHANNEL_ENV = "LAST30DAYS_BROWSER_CHANNEL"
_DISABLE_BROWSER_ENV = "LAST30DAYS_DISABLE_BROWSER"
_CONCURRENCY_ENV = "LAST30DAYS_BROWSER_CONCURRENCY"

_DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)
_MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1"
)

_failure_lock = threading.Lock()
_browser_failure: Optional[str] = None
_failure_reported = False
_semaphore: Optional[threading.BoundedSemaphore] = None
_semaphore_lock = threading.Lock()

# Platform login metadata. ``cookies``: names that only exist after a real login.
# For XHS/Weibo anonymous visitors also receive session-like cookies, so we rely
# on the marker written by a successful ``login`` run plus an in-page check.
LOGIN_SPECS: Dict[str, Dict[str, Any]] = {
    "xiaohongshu": {
        "label": "小红书",
        "url": "https://www.xiaohongshu.com/explore",
        "domain": ".xiaohongshu.com",
        "cookies": ("web_session",),
        "anonymous_cookie_ambiguous": True,
    },
    "weibo": {
        "label": "微博",
        "url": "https://passport.weibo.com/sso/signin?entry=wapsso&source=wapssowb&url=https%3A%2F%2Fm.weibo.cn%2F",
        "domain": ".weibo.cn",
        "extra_domains": (".weibo.com",),
        "cookies": ("SUB",),
        "anonymous_cookie_ambiguous": True,
    },
    "zhihu": {
        "label": "知乎",
        "url": "https://www.zhihu.com/signin",
        "domain": ".zhihu.com",
        "cookies": ("z_c0",),
    },
    "douyin": {
        "label": "抖音",
        "url": "https://www.douyin.com/",
        "domain": ".douyin.com",
        "cookies": ("sessionid", "sessionid_ss"),
    },
    "bilibili": {
        "label": "B站",
        "url": "https://passport.bilibili.com/login",
        "domain": ".bilibili.com",
        "cookies": ("SESSDATA",),
    },
}

_LOGIN_WALL_MARKERS = ("扫码登录", "登录后查看", "请登录", "登录后即可", "手机号登录")


# ---------------------------------------------------------------------------
# Availability, health and launch options
# ---------------------------------------------------------------------------

def _browser_disabled() -> bool:
    return os.environ.get(_DISABLE_BROWSER_ENV, "").lower() in ("1", "true", "yes", "on")


def is_playwright_available() -> bool:
    """Playwright 已安装、未被禁用，且本次运行中浏览器没有启动失败。"""
    global _playwright_available
    if _browser_failure is not None:
        return False
    if _playwright_available is not None:
        return _playwright_available
    if _browser_disabled():
        _playwright_available = False
        return _playwright_available
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
        _playwright_available = True
    except (ImportError, OSError):
        _playwright_available = False
    return _playwright_available


def browser_failure() -> Optional[str]:
    """Reason the browser failed to launch in this run (circuit breaker)."""
    return _browser_failure


def reset_browser_failure() -> None:
    global _browser_failure, _failure_reported
    with _failure_lock:
        _browser_failure = None
        _failure_reported = False


def _mark_browser_failure(reason: str) -> None:
    global _browser_failure, _failure_reported
    with _failure_lock:
        if _browser_failure is None:
            _browser_failure = reason
        if _failure_reported:
            return
        _failure_reported = True
    sys.stderr.write(
        "[浏览器] 无法启动 Playwright 浏览器，本次运行将自动切换为无浏览器模式。\n"
        f"         原因: {reason[:300]}\n"
        "         旧电脑/旧 macOS：设置 LAST30DAYS_BROWSER_PATH 指向本机可运行的 Chrome/Chromium，"
        "或 LAST30DAYS_BROWSER_CHANNEL=chrome；完全关闭浏览器：LAST30DAYS_DISABLE_BROWSER=1。\n"
        "         新机器：python -m playwright install chromium\n"
    )


def _get_semaphore() -> threading.BoundedSemaphore:
    global _semaphore
    with _semaphore_lock:
        if _semaphore is None:
            try:
                size = int(os.environ.get(_CONCURRENCY_ENV, "2"))
            except ValueError:
                size = 2
            _semaphore = threading.BoundedSemaphore(max(1, size))
        return _semaphore


def _browser_launch_kwargs() -> Dict[str, Any]:
    """Return optional Playwright launch overrides for old machines."""
    kwargs: Dict[str, Any] = {}
    browser_path = os.environ.get(_BROWSER_PATH_ENV, "").strip()
    browser_channel = os.environ.get(_BROWSER_CHANNEL_ENV, "").strip()
    if browser_path:
        kwargs["executable_path"] = os.path.expanduser(browser_path)
    elif browser_channel:
        kwargs["channel"] = browser_channel
    return kwargs


def _browser_status() -> Dict[str, Any]:
    """Describe the selected browser without starting it."""
    browser_path = os.environ.get(_BROWSER_PATH_ENV, "").strip()
    browser_channel = os.environ.get(_BROWSER_CHANNEL_ENV, "").strip()
    disabled = _browser_disabled()
    expanded_path = os.path.expanduser(browser_path) if browser_path else ""
    return {
        "mode": "disabled" if disabled else ("external-path" if browser_path else ("channel" if browser_channel else "managed")),
        "path": expanded_path or None,
        "path_exists": bool(expanded_path and Path(expanded_path).is_file()),
        "channel": browser_channel or None,
        "disable_env": _DISABLE_BROWSER_ENV,
        "concurrency": os.environ.get(_CONCURRENCY_ENV, "2"),
        "launch_failure": _browser_failure,
    }


def _ua_for_browser(version: str, mobile: bool) -> str:
    if mobile:
        return _MOBILE_UA
    major = (version or "").split(".", 1)[0]
    if not major.isdigit():
        return _DESKTOP_UA
    system = platform_mod.system()
    if system == "Darwin":
        os_part = "Macintosh; Intel Mac OS X 10_15_7"
    elif system == "Linux":
        os_part = "X11; Linux x86_64"
    else:
        os_part = "Windows NT 10.0; Win64; x64"
    return f"Mozilla/5.0 ({os_part}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{major}.0.0.0 Safari/537.36"


# ---------------------------------------------------------------------------
# Cookie / login-state persistence
# ---------------------------------------------------------------------------

def _ensure_cookie_dir():
    COOKIE_DIR.mkdir(parents=True, exist_ok=True)


def _get_cookie_path(platform: str) -> Path:
    _ensure_cookie_dir()
    return COOKIE_DIR / f"{platform}_cookies.json"


def _marker_path(platform: str) -> Path:
    _ensure_cookie_dir()
    return COOKIE_DIR / f"{platform}_login.json"


def _write_private(path: Path, text: str) -> None:
    """Write a file readable only by the current user (cookies are secrets)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name, dir=str(path.parent))
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        tmp.write_text(text, encoding="utf-8")
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def save_cookies(platform: str, cookies: list):
    path = _get_cookie_path(platform)
    _write_private(path, json.dumps(cookies, ensure_ascii=False, indent=2))


def load_cookies(platform: str) -> Optional[list]:
    path = COOKIE_DIR / f"{platform}_cookies.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def _cookie_alive(cookie: Dict[str, Any], now: Optional[float] = None) -> bool:
    expires = cookie.get("expires")
    if expires in (None, -1, 0):
        return True
    try:
        return float(expires) > (now or time.time())
    except (TypeError, ValueError):
        return True


def has_login(platform: str) -> bool:
    """True when a saved session for ``platform`` still carries login cookies."""
    spec = LOGIN_SPECS.get(platform)
    if not spec:
        return False
    cookies = load_cookies(platform) or []
    names = {c.get("name") for c in cookies if isinstance(c, dict) and _cookie_alive(c)}
    if not any(name in names for name in spec["cookies"]):
        return False
    if spec.get("anonymous_cookie_ambiguous"):
        return (COOKIE_DIR / f"{platform}_login.json").exists()
    return True


def login_status(platform: str) -> Dict[str, Any]:
    spec = LOGIN_SPECS.get(platform, {})
    cookies = load_cookies(platform) or []
    marker = {}
    path = COOKIE_DIR / f"{platform}_login.json"
    if path.exists():
        try:
            marker = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            marker = {}
    expiries = [
        c.get("expires") for c in cookies
        if isinstance(c, dict) and c.get("name") in spec.get("cookies", ()) and isinstance(c.get("expires"), (int, float)) and c.get("expires") > 0
    ]
    expires_at = None
    if expiries:
        expires_at = datetime.fromtimestamp(min(expiries), tz=dates.CST).strftime("%Y-%m-%d")
    return {
        "platform": platform,
        "label": spec.get("label", platform),
        "logged_in": has_login(platform),
        "cookie_count": len(cookies),
        "login_saved_at": marker.get("saved_at"),
        "login_method": marker.get("method"),
        "expires": expires_at,
    }


def _write_marker(platform: str, method: str) -> None:
    payload = {"saved_at": datetime.now(dates.CST).strftime("%Y-%m-%d %H:%M"), "method": method}
    _write_private(_marker_path(platform), json.dumps(payload, ensure_ascii=False))


def mark_logged_out(platform: str) -> None:
    """Forget a login marker after the platform showed a login wall again."""
    path = COOKIE_DIR / f"{platform}_login.json"
    try:
        if path.exists():
            path.unlink()
    except OSError:
        pass


def import_cookie_header(platform: str, cookie_header: str) -> int:
    """Import a browser-copied ``a=1; b=2`` cookie string as a saved login."""
    spec = LOGIN_SPECS.get(platform)
    if not spec:
        raise ValueError(f"未知平台: {platform}")
    domains = (spec["domain"],) + tuple(spec.get("extra_domains", ()))
    cookies = []
    for part in (cookie_header or "").split(";"):
        if "=" not in part:
            continue
        name, _, value = part.strip().partition("=")
        name = name.strip()
        if not name:
            continue
        for domain in domains:
            cookies.append({
                "name": name,
                "value": value.strip(),
                "domain": domain,
                "path": "/",
                "expires": -1,
                "httpOnly": False,
                "secure": True,
                "sameSite": "Lax",
            })
    if not cookies:
        return 0
    names = {c["name"] for c in cookies}
    if not any(name in names for name in spec["cookies"]):
        raise ValueError(
            f"Cookie 中缺少 {spec['label']} 登录字段（需要 {' 或 '.join(spec['cookies'])}），"
            "请在已登录的浏览器里复制完整 Cookie"
        )
    save_cookies(platform, cookies)
    _write_marker(platform, "cookie-import")
    return len(names)


# ---------------------------------------------------------------------------
# Browser context
# ---------------------------------------------------------------------------

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

    if _browser_failure is not None:
        raise RuntimeError(f"浏览器已在本次运行中启动失败: {_browser_failure}")

    viewport = {"width": 390, "height": 844} if mobile else {"width": 1366, "height": 860}
    semaphore = _get_semaphore()
    semaphore.acquire()
    try:
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(
                    headless=headless,
                    args=["--disable-blink-features=AutomationControlled"],
                    **_browser_launch_kwargs(),
                )
            except Exception as exc:
                _mark_browser_failure(f"{type(exc).__name__}: {exc}")
                raise
            try:
                context_kwargs: Dict[str, Any] = {
                    "user_agent": _ua_for_browser(getattr(browser, "version", ""), mobile),
                    "locale": "zh-CN",
                    "timezone_id": "Asia/Shanghai",
                    "viewport": viewport,
                }
                if mobile:
                    context_kwargs.update({"is_mobile": True, "has_touch": True, "device_scale_factor": 3})
                context = browser.new_context(**context_kwargs)
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
    finally:
        semaphore.release()


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


def _page_text(page, limit: int = 4000) -> str:
    try:
        return (page.inner_text("body") or "")[:limit]
    except Exception:
        return ""


def _looks_like_login_wall(page) -> bool:
    try:
        url = page.url or ""
    except Exception:
        url = ""
    if any(token in url for token in ("/signin", "passport.", "/login")):
        return True
    text = _page_text(page)
    return any(marker in text for marker in _LOGIN_WALL_MARKERS)


# ---------------------------------------------------------------------------
# Interactive login
# ---------------------------------------------------------------------------

_LOGIN_JS_CHECKS = {
    "xiaohongshu": """() => {
        const s = window.__INITIAL_STATE__;
        try {
            const user = s && s.user;
            const flag = user && (user.loggedIn && (user.loggedIn._value ?? user.loggedIn.value ?? user.loggedIn));
            if (flag === true) return true;
            const info = user && (user.userInfo && (user.userInfo._value || user.userInfo.value || user.userInfo));
            return !!(info && (info.user_id || info.userId) && !info.guest);
        } catch (e) { return false; }
    }""",
}


def _logged_in_now(platform: str, page, context, baseline: Dict[str, str]) -> bool:
    spec = LOGIN_SPECS[platform]
    cookies = {c.get("name"): c.get("value") for c in context.cookies()}
    if platform == "weibo":
        try:
            info = page.evaluate(
                "async () => { try { const r = await fetch('https://m.weibo.cn/api/config', {credentials: 'include'});"
                " const j = await r.json(); return !!(j && j.data && j.data.login); } catch (e) { return false; } }"
            )
            return bool(info)
        except Exception:
            return False
    if platform == "xiaohongshu":
        session = cookies.get("web_session")
        if session and session != baseline.get("web_session"):
            return True
        try:
            return bool(page.evaluate(_LOGIN_JS_CHECKS["xiaohongshu"]))
        except Exception:
            return False
    return any(cookies.get(name) for name in spec["cookies"])


def interactive_login(platform: str, timeout_seconds: int = 240) -> Tuple[bool, str]:
    """打开可见浏览器，等待用户完成登录并保存登录态。"""
    spec = LOGIN_SPECS.get(platform)
    if not spec:
        return False, f"未知平台 {platform}；可选: {', '.join(LOGIN_SPECS)}"
    if _browser_disabled():
        return False, "已设置 LAST30DAYS_DISABLE_BROWSER=1；请改用 --cookie 导入浏览器复制的 Cookie"
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except (ImportError, OSError):
        return False, (
            "未安装 Playwright：python -m pip install playwright && python -m playwright install chromium；"
            "或改用 `login <平台> --cookie \"...\"` 导入 Cookie"
        )

    label = spec["label"]
    sys.stderr.write(
        f"[登录] 正在打开浏览器，请在窗口中完成{label}登录（扫码或账号密码），"
        f"最长等待 {timeout_seconds} 秒...\n"
    )
    try:
        with _launch_browser_context(platform, headless=False) as (_browser, context, page):
            baseline = {c.get("name"): c.get("value") for c in context.cookies()}
            try:
                page.goto(spec["url"], wait_until="domcontentloaded", timeout=30000)
            except Exception as exc:
                sys.stderr.write(f"[登录] 打开登录页失败（可继续手动打开）: {exc}\n")
            page.wait_for_timeout(2000)
            baseline.update({c.get("name"): c.get("value") for c in context.cookies() if c.get("name") not in baseline})
            deadline = time.time() + timeout_seconds
            while time.time() < deadline:
                if _logged_in_now(platform, page, context, baseline):
                    page.wait_for_timeout(1500)
                    save_cookies(platform, context.cookies())
                    _write_marker(platform, "browser")
                    return True, f"{label}登录成功，登录态已保存到 {COOKIE_DIR}"
                try:
                    page.wait_for_timeout(2000)
                except Exception:
                    break
    except Exception as exc:
        reason = f"{type(exc).__name__}: {exc}"
        if "display" in reason.lower() or "headed" in reason.lower() or "xserver" in reason.lower():
            reason += "；当前环境没有图形界面，请改用 `login <平台> --cookie \"...\"`"
        return False, f"{label}登录失败: {reason}"
    return False, f"{label}登录超时（{timeout_seconds} 秒内未检测到登录）"


# ---------------------------------------------------------------------------
# Weibo
# ---------------------------------------------------------------------------

def crawl_weibo(topic: str, limit: int = 20) -> List[Dict[str, Any]]:
    """通过浏览器（复用登录态）搜索微博。"""
    if not is_playwright_available():
        return []
    from . import weibo as weibo_mod

    items: List[Dict[str, Any]] = []
    try:
        with _launch_browser_context("weibo", mobile=True) as (browser, context, page):
            page.goto("https://m.weibo.cn/", wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(1200)
            logged_in = page.evaluate(
                "async () => { try { const r = await fetch('/api/config'); const j = await r.json();"
                " return !!(j && j.data && j.data.login); } catch (e) { return false; } }"
            )
            if not logged_in:
                mark_logged_out("weibo")
                sys.stderr.write(f"[爬虫-微博] 浏览器未登录微博；{weibo_mod.LOGIN_HINT}\n")
                return []
            for page_no in (1, 2):
                params = {"containerid": f"100103type=1&q={topic}", "page_type": "searchall"}
                if page_no > 1:
                    params["page"] = str(page_no)
                url = "/api/container/getIndex?" + urllib.parse.urlencode(params)
                response = page.evaluate(
                    "async (url) => { const r = await fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}});"
                    " return await r.json(); }",
                    url,
                )
                if not isinstance(response, dict):
                    break
                batch = weibo_mod.parse_mobile_cards(response)
                for item in batch:
                    item["source"] = "crawler"
                items.extend(batch)
                if not batch or len(items) >= limit:
                    break
                page.wait_for_timeout(800)
    except Exception as e:
        sys.stderr.write(f"[爬虫-微博] 浏览器爬取失败: {e}\n")
    return items[:limit]


def _parse_weibo_mblog(mblog: dict) -> Dict[str, Any]:
    text = _clean_html(mblog.get("text", ""))
    user = mblog.get("user", {}) or {}
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


# ---------------------------------------------------------------------------
# Xiaohongshu
# ---------------------------------------------------------------------------

_XHS_STATE_JS = """() => {
    const s = window.__INITIAL_STATE__;
    if (!s || !s.search) return null;
    let feeds = s.search.feeds;
    if (feeds && feeds._value !== undefined) feeds = feeds._value;
    if (feeds && feeds.value !== undefined && !Array.isArray(feeds)) feeds = feeds.value;
    try { return JSON.parse(JSON.stringify(feeds || [])); } catch (e) { return null; }
}"""


def crawl_xiaohongshu(topic: str, limit: int = 20) -> List[Dict[str, Any]]:
    """通过浏览器（复用登录态）爬取小红书搜索结果。

    解析顺序：搜索 XHR 中的笔记卡片 → ``window.__INITIAL_STATE__.search.feeds``
    → DOM。``search/recommend`` 只返回联想词（``sug_items``），不会被当成笔记。
    """
    if not is_playwright_available():
        return []
    from . import xiaohongshu as xhs_mod

    items: List[Dict[str, Any]] = []
    try:
        with _launch_browser_context("xiaohongshu") as (browser, context, page):
            captured: Dict[str, Any] = {"items": [], "endpoint": ""}

            def _on_response(resp):
                try:
                    url = resp.url
                    lowered = url.lower()
                    if resp.status != 200 or "xiaohongshu.com" not in lowered:
                        return
                    if "/api/" not in lowered or "search" not in lowered:
                        return
                    payload = resp.json()
                    note_items = _extract_xhs_note_items(payload)
                    if note_items and not captured["items"]:
                        captured["items"] = note_items
                        captured["endpoint"] = url.split("?", 1)[0]
                except Exception:
                    pass

            page.on("response", _on_response)

            search_url = (
                "https://www.xiaohongshu.com/search_result?"
                f"keyword={urllib.parse.quote(topic, safe='')}&source=web_search_result_notes"
            )
            try:
                page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            except Exception as e:
                sys.stderr.write(f"[爬虫-小红书] 页面加载失败: {e}\n")

            state_items: List[Any] = []

            def _read_state() -> bool:
                nonlocal state_items
                try:
                    feeds = page.evaluate(_XHS_STATE_JS)
                except Exception:
                    feeds = None
                if isinstance(feeds, list) and feeds:
                    state_items = feeds
                    return True
                return False

            _wait_for(page, lambda: bool(captured["items"]) or _read_state(), timeout_ms=6000)
            if not captured["items"] and not state_items:
                _submit_xhs_search(page, topic)
                for _ in range(6):
                    if captured["items"] or _read_state():
                        break
                    try:
                        page.mouse.wheel(0, 2000)
                    except Exception:
                        pass
                    page.wait_for_timeout(1000)

            for raw in captured["items"][:limit]:
                parsed = _parse_crawler_xhs_note(raw)
                if parsed:
                    items.append(parsed)

            if not items and state_items:
                for feed in state_items[:limit]:
                    parsed = xhs_mod.parse_mcp_feed(feed)
                    if parsed and parsed.get("title"):
                        parsed["source"] = "crawler-state"
                        items.append(parsed)

            if not items:
                items = _xhs_dom_items(page, limit)

            if not items:
                if _looks_like_login_wall(page):
                    mark_logged_out("xiaohongshu")
                    sys.stderr.write(f"[爬虫-小红书] 页面要求登录；{xhs_mod.LOGIN_HINT}\n")
                else:
                    sys.stderr.write(
                        "[爬虫-小红书] 未解析到笔记卡片（可能遇到验证码、风控或页面改版）；"
                        "将继续尝试公开搜索兜底。\n"
                    )
    except Exception as e:
        sys.stderr.write(f"[爬虫-小红书] 浏览器爬取失败: {e}\n")
    return items


def _xhs_dom_items(page, limit: int) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    try:
        note_elements = page.query_selector_all("section.note-item")
    except Exception:
        return items
    for elem in note_elements[:limit]:
        try:
            link_el = elem.query_selector("a[href*='/search_result/'], a[href*='/explore/']")
            link = link_el.get_attribute("href") if link_el else ""
            if link and not link.startswith("http"):
                link = f"https://www.xiaohongshu.com{link}"
            match = re.search(r"/(?:explore|search_result)/([0-9a-f]{24})", link or "")
            if match and "xsec_token" not in link:
                link = f"https://www.xiaohongshu.com/explore/{match.group(1)}"
            title_el = elem.query_selector("a.title span, span[class*='title'], div[class*='title']")
            title = title_el.inner_text() if title_el else ""
            author_el = elem.query_selector("span.name, span[class*='name'], div[class*='author']")
            likes_el = elem.query_selector("span.count, span[class*='like'] span, span[class*='count']")
            if not title or not link:
                continue
            items.append({
                "title": title.strip(),
                "desc": "",
                "url": link,
                "author_name": (author_el.inner_text() if author_el else "").strip(),
                "author_id": "",
                "date": None,
                "engagement": {
                    "likes": _parse_count(likes_el.inner_text() if likes_el else "0"),
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
    return items


def _submit_xhs_search(page, topic: str) -> bool:
    """Submit the search box when the page does not auto-run the query."""
    selectors = (
        "input#search-input",
        "input[placeholder*='搜索']",
        "input[placeholder*='搜']",
        "input[type='search']",
    )
    for selector in selectors:
        try:
            for element in page.query_selector_all(selector):
                if not element.is_visible():
                    continue
                element.fill(topic)
                element.press("Enter")
                return True
        except Exception:
            continue
    return False


def _extract_xhs_note_items(payload: Any) -> List[Dict[str, Any]]:
    """Find note-card records in changing XHS search response envelopes."""
    def is_note_record(value: Any) -> bool:
        if not isinstance(value, dict):
            return False
        card = value.get("note_card") or value.get("noteCard")
        if isinstance(card, dict):
            return bool(
                (card.get("note_id") or card.get("noteId") or value.get("id"))
                and (card.get("title") or card.get("display_title") or card.get("displayTitle") or card.get("desc"))
            )
        return bool(
            (value.get("note_id") or value.get("id"))
            and (value.get("title") or value.get("display_title") or value.get("desc"))
        )

    def walk(value: Any) -> List[Dict[str, Any]]:
        if isinstance(value, list):
            records = [item for item in value if is_note_record(item)]
            if records:
                return records
            for item in value:
                records = walk(item)
                if records:
                    return records
        elif isinstance(value, dict):
            for child in value.values():
                records = walk(child)
                if records:
                    return records
        return []

    return walk(payload)


def _parse_crawler_xhs_note(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Normalize one XHS note-card record captured by Playwright."""
    from .xiaohongshu import note_url

    card = raw.get("note_card") or raw.get("noteCard")
    note_card = card if isinstance(card, dict) else raw
    note_id = raw.get("id") or note_card.get("note_id") or note_card.get("noteId") or raw.get("note_id", "")
    if not note_id:
        return None
    user = note_card.get("user") or raw.get("user") or {}
    interact = note_card.get("interact_info") or note_card.get("interactInfo") or raw.get("interact_info") or {}
    xsec = raw.get("xsec_token") or raw.get("xsecToken") or ""
    ts = note_card.get("time") or note_card.get("last_update_time")
    date_str = None
    if ts:
        try:
            value = int(ts)
            date_str = dates.timestamp_to_date(value / 1000 if value > 10_000_000_000 else value)
        except (TypeError, ValueError):
            date_str = None
    return {
        "title": note_card.get("display_title") or note_card.get("displayTitle") or note_card.get("title") or raw.get("title", ""),
        "desc": note_card.get("desc") or note_card.get("description") or raw.get("desc", ""),
        "url": note_url(str(note_id), xsec),
        "author_name": user.get("nickname") or user.get("nick_name") or user.get("name", ""),
        "author_id": user.get("user_id") or user.get("userid") or user.get("userId") or user.get("id", ""),
        "date": date_str,
        "engagement": {
            "likes": _parse_count(str(interact.get("liked_count", interact.get("likedCount", raw.get("liked_count", "0"))))),
            "collects": _parse_count(str(interact.get("collected_count", interact.get("collectedCount", raw.get("collected_count", "0"))))),
            "comments": _parse_count(str(interact.get("comment_count", interact.get("commentCount", raw.get("comment_count", "0"))))),
            "shares": _parse_count(str(interact.get("share_count", interact.get("sharedCount", raw.get("share_count", "0"))))),
        },
        "hashtags": [],
        "images": [
            img.get("url_default") or img.get("url", "")
            for img in (note_card.get("image_list") or raw.get("image_list") or [])
            if isinstance(img, dict)
        ],
        "source": "crawler-xhr",
    }


# ---------------------------------------------------------------------------
# Douyin
# ---------------------------------------------------------------------------

_DOUYIN_SEARCH_XHR = ("/aweme/v1/web/search/item", "/aweme/v1/web/general/search/single")


def crawl_douyin(topic: str, limit: int = 20) -> List[Dict[str, Any]]:
    """通过浏览器（复用登录态）爬取抖音搜索结果；由页面自己完成签名。"""
    if not is_playwright_available():
        return []
    from . import douyin as douyin_mod

    items: List[Dict[str, Any]] = []
    try:
        with _launch_browser_context("douyin") as (browser, context, page):
            captured: List[Dict[str, Any]] = []

            def _on_response(resp):
                try:
                    if resp.status != 200 or not any(path in resp.url for path in _DOUYIN_SEARCH_XHR):
                        return
                    data = resp.json()
                    for entry in (data or {}).get("data") or []:
                        aweme = entry.get("aweme_info") if isinstance(entry, dict) else None
                        if isinstance(aweme, dict) and aweme.get("aweme_id"):
                            captured.append(aweme)
                except Exception:
                    pass

            page.on("response", _on_response)
            search_url = f"https://www.douyin.com/search/{urllib.parse.quote(topic)}?type=video"
            try:
                page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            except Exception as e:
                sys.stderr.write(f"[爬虫-抖音] 页面加载失败: {e}\n")

            for _ in range(8):
                if len(captured) >= limit:
                    break
                try:
                    page.mouse.wheel(0, 2400)
                except Exception:
                    pass
                page.wait_for_timeout(1200)

            seen = set()
            for aweme in captured:
                if aweme.get("aweme_id") in seen:
                    continue
                seen.add(aweme.get("aweme_id"))
                parsed = douyin_mod.parse_aweme(aweme, source="crawler-xhr")
                items.append(parsed)
                if len(items) >= limit:
                    break

            if not items:
                text = _page_text(page)
                if "验证" in text or "captcha" in (page.url or ""):
                    sys.stderr.write("[爬虫-抖音] 遇到验证码/风控；可运行 login douyin 后重试。\n")
                elif _looks_like_login_wall(page) or not has_login("douyin"):
                    sys.stderr.write(f"[爬虫-抖音] 未拿到搜索结果；{douyin_mod.LOGIN_HINT}\n")
    except Exception as e:
        sys.stderr.write(f"[爬虫-抖音] 浏览器爬取失败: {e}\n")
    return items


# ---------------------------------------------------------------------------
# Bilibili
# ---------------------------------------------------------------------------

def crawl_bilibili(topic: str, limit: int = 20) -> List[Dict[str, Any]]:
    """通过浏览器爬取B站搜索结果（拦截页面自己的 WBI 搜索请求，DOM 兜底）。"""
    if not is_playwright_available():
        return []
    from . import bilibili as bili_mod

    items: List[Dict[str, Any]] = []
    try:
        with _launch_browser_context("bilibili") as (browser, context, page):
            captured: List[Dict[str, Any]] = []

            def _on_response(resp):
                try:
                    if resp.status != 200 or "/x/web-interface/" not in resp.url or "search" not in resp.url:
                        return
                    data = resp.json()
                    result = ((data or {}).get("data") or {}).get("result") or []
                    for entry in result:
                        if isinstance(entry, dict) and entry.get("bvid"):
                            captured.append(entry)
                        elif isinstance(entry, dict) and entry.get("result_type") == "video":
                            captured.extend(v for v in entry.get("data") or [] if isinstance(v, dict) and v.get("bvid"))
                except Exception:
                    pass

            page.on("response", _on_response)
            search_url = f"https://search.bilibili.com/video?keyword={urllib.parse.quote(topic)}&order=totalrank"
            try:
                page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            except Exception as e:
                sys.stderr.write(f"[爬虫-B站] 页面加载失败: {e}\n")
            _wait_for(page, lambda: bool(captured) or bool(page.query_selector("div.bili-video-card")), timeout_ms=8000)

            for entry in captured[:limit]:
                parsed = bili_mod._parse_video(entry)
                parsed["source"] = "crawler-xhr"
                items.append(parsed)

            if not items:
                for elem in page.query_selector_all("div.bili-video-card")[:limit]:
                    try:
                        title_el = elem.query_selector("h3[class*='title'], a[class*='title']")
                        link_el = elem.query_selector("a[href*='/video/']")
                        href = link_el.get_attribute("href") if link_el else ""
                        if href.startswith("//"):
                            href = "https:" + href
                        elif href.startswith("/"):
                            href = "https://www.bilibili.com" + href
                        author_el = elem.query_selector("span.bili-video-card__info--author, span[class*='name']")
                        views_el = elem.query_selector("span.bili-video-card__stats--item span, span[class*='play']")
                        bvid_match = re.search(r"(BV[0-9A-Za-z]{10})", href or "")
                        items.append({
                            "title": _clean_html(title_el.inner_text()) if title_el else "",
                            "url": href,
                            "bvid": bvid_match.group(1) if bvid_match else "",
                            "channel_name": author_el.inner_text() if author_el else "",
                            "author_mid": "",
                            "date": None,
                            "duration": None,
                            "description": "",
                            "engagement": {"views": _parse_count(views_el.inner_text() if views_el else "0")},
                            "source": "crawler-dom",
                        })
                    except Exception:
                        continue
    except Exception as e:
        sys.stderr.write(f"[爬虫-B站] 浏览器爬取失败: {e}\n")
    return [item for item in items if item.get("title") and item.get("url")]


# ---------------------------------------------------------------------------
# Zhihu
# ---------------------------------------------------------------------------

def crawl_zhihu(topic: str, limit: int = 20) -> List[Dict[str, Any]]:
    """通过浏览器（复用登录态）爬取知乎搜索结果（拦截 search_v3 XHR）。"""
    if not is_playwright_available():
        return []
    from . import zhihu as zhihu_mod

    items: List[Dict[str, Any]] = []
    try:
        with _launch_browser_context("zhihu") as (browser, context, page):
            captured: List[Any] = []

            def _on_response(resp):
                try:
                    if resp.status == 200 and "/api/v4/search_v3" in resp.url:
                        captured.append(resp.json())
                except Exception:
                    pass

            page.on("response", _on_response)
            search_url = f"https://www.zhihu.com/search?type=content&q={urllib.parse.quote(topic)}"
            try:
                page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            except Exception as e:
                sys.stderr.write(f"[爬虫-知乎] 页面加载失败: {e}\n")
            _wait_for(page, lambda: bool(captured), timeout_ms=8000)
            if captured:
                try:
                    page.mouse.wheel(0, 2400)
                    page.wait_for_timeout(1500)
                except Exception:
                    pass

            seen = set()
            for payload in captured:
                for parsed in zhihu_mod.parse_search_payload(payload):
                    if parsed["url"] in seen:
                        continue
                    seen.add(parsed["url"])
                    parsed["source"] = "crawler-xhr"
                    items.append(parsed)

            if not items:
                items = _zhihu_dom_items(page, limit)

            if not items:
                if _looks_like_login_wall(page):
                    mark_logged_out("zhihu")
                    sys.stderr.write(f"[爬虫-知乎] 页面要求登录；{zhihu_mod.LOGIN_HINT}\n")
                else:
                    sys.stderr.write(
                        "[爬虫-知乎] Playwright 未解析到结果；可能是登录态失效、反爬验证或页面结构变更。\n"
                    )
    except Exception as e:
        sys.stderr.write(f"[爬虫-知乎] 浏览器爬取失败: {e}\n")
    return items[:limit]


def _zhihu_dom_items(page, limit: int) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    try:
        result_elements = page.query_selector_all("div.SearchResult-Card, div[class*='List-item']")
    except Exception:
        return items
    for elem in result_elements[:limit]:
        try:
            title_el = elem.query_selector("h2[class*='ContentItem-title'], span[class*='Highlight']")
            title = _clean_html(title_el.inner_text()) if title_el else ""
            link_el = elem.query_selector("a[href*='/question/'], a[href*='/p/']")
            link = link_el.get_attribute("href") if link_el else ""
            if link and link.startswith("//"):
                link = "https:" + link
            elif link and link.startswith("/"):
                link = f"https://www.zhihu.com{link}"
            excerpt_el = elem.query_selector("span[class*='RichText'], div[class*='RichText']")
            voteup_el = elem.query_selector("button[class*='VoteButton'] span, span[class*='vote']")
            if not title or not link:
                continue
            items.append({
                "title": title,
                "excerpt": _clean_html(excerpt_el.inner_text()[:300]) if excerpt_el else "",
                "url": link,
                "author": "",
                "date": None,
                "content_type": "search_result",
                "engagement": {
                    "voteups": _parse_count(voteup_el.inner_text() if voteup_el else "0"),
                    "comments": 0,
                    "collects": 0,
                },
                "source": "crawler-dom",
            })
        except Exception:
            continue
    return items


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _parse_count(text: str) -> int:
    """解析数量文本，支持 '1.2万' / '1.2w' / '12k' / '10+' 等格式。"""
    if not text:
        return 0
    text = str(text).strip().replace(",", "").rstrip("+")
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
        return int(float(re.sub(r"[^\d.]", "", text or "0") or 0))
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

    if "刚刚" in date_str:
        return now.strftime("%Y-%m-%d")
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
    logins: Dict[str, Any] = {}

    if COOKIE_DIR.exists():
        for f in COOKIE_DIR.glob("*_cookies.json"):
            platform = f.stem.replace("_cookies", "")
            cached_platforms.append(platform)
        for platform in LOGIN_SPECS:
            if (COOKIE_DIR / f"{platform}_cookies.json").exists():
                try:
                    logins[platform] = login_status(platform)
                except Exception:
                    pass

    return {
        "playwright_available": pw_available,
        "cached_logins": sorted(cached_platforms),
        "logins": logins,
        "cookie_dir": str(COOKIE_DIR),
        "browser": _browser_status(),
    }


def probe_browser_launch(timeout_ms: int = 30000) -> Tuple[bool, str]:
    """Actually start and close the configured browser (for --diagnose)."""
    if _browser_disabled():
        return False, "已通过 LAST30DAYS_DISABLE_BROWSER 禁用"
    try:
        from playwright.sync_api import sync_playwright
    except (ImportError, OSError) as exc:
        return False, f"Playwright 未安装: {exc}"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, timeout=timeout_ms, **_browser_launch_kwargs())
            version = getattr(browser, "version", "")
            browser.close()
        return True, f"浏览器可启动（Chromium {version}）"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {str(exc)[:300]}"
