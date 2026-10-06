"""HTTP utilities for last30days-cn (stdlib only).

Author: Jesse (https://github.com/Jesseovo)

v4 changes:
- Complete, browser-grade User-Agent strings live here and only here. Several
  platform WAFs (Bilibili first, see issue #17) now answer truncated UAs such as
  ``Mozilla/5.0 (...) AppleWebKit/537.36`` with HTTP 412.
- ``browser_headers()`` builds consistent desktop/mobile header sets
  (UA + client hints + Accept-Language) for platform requests.
- gzip/deflate decoding and charset detection (GBK pages decode correctly).
- ``Session`` keeps cookies across requests (visitor cookies, buvid3, ...).
- 412 / anti-bot responses fail fast instead of burning retries.
- ``--debug`` now takes effect even though modules are imported before
  argparse runs (the flag used to be read once at import time).
"""

import gzip
import http.cookiejar
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .version import VERSION

DEFAULT_TIMEOUT = 30
MAX_RETRIES = 3
RETRY_DELAY = 2.0
RETRY_BACKOFF = 2.0
RETRY_CAP = 30.0
RETRY_AFTER_CAP = 60.0
SECRET_QUERY_KEYS = ("key", "token", "secret", "password", "auth", "cookie", "sessdata")

# Honest tool identity, used for open APIs that ask clients to identify
# themselves (Hacker News Algolia, GitHub, Reddit, self-hosted MCP servers).
USER_AGENT = f"last30days-cn/{VERSION} (Research Skill; +https://github.com/Jesseovo/last30days-skill-cn)"

# Browser identities for Chinese platform pages. Keep these complete: WAFs
# reject UAs that stop after "AppleWebKit/537.36" (issue #17).
CHROME_MAJOR = "140"
DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    f"(KHTML, like Gecko) Chrome/{CHROME_MAJOR}.0.0.0 Safari/537.36"
)
MAC_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    f"(KHTML, like Gecko) Chrome/{CHROME_MAJOR}.0.0.0 Safari/537.36"
)
MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1"
)

_UA_OVERRIDE_ENV = "LAST30DAYS_USER_AGENT"

# Markers of interstitial / anti-bot pages that should not be parsed as results.
ANTIBOT_MARKERS = (
    "百度安全验证",
    "wappass.baidu.com",
    "Sina Visitor System",
    "antispider",
    "验证码",
    "安全验证",
    "访问过于频繁",
    "请求存在异常",
    "unusual traffic",
)


def _debug_enabled() -> bool:
    return os.environ.get("LAST30DAYS_DEBUG", "").lower() in ("1", "true", "yes")


# Kept for backward compatibility; prefer _debug_enabled() which is dynamic.
DEBUG = _debug_enabled()


def log(msg: str):
    """Log debug message to stderr (enabled by --debug / LAST30DAYS_DEBUG=1)."""
    if _debug_enabled():
        sys.stderr.write(f"[DEBUG] {msg}\n")
        sys.stderr.flush()


class HTTPError(Exception):
    """HTTP request error with status code."""

    def __init__(self, message: str, status_code: Optional[int] = None, body: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body

    @property
    def code(self) -> Optional[int]:
        """Alias matching urllib.error.HTTPError.code."""
        return self.status_code


def desktop_ua() -> str:
    """Desktop UA, overridable with LAST30DAYS_USER_AGENT."""
    return os.environ.get(_UA_OVERRIDE_ENV, "").strip() or DESKTOP_UA


def mobile_ua() -> str:
    return MOBILE_UA


def browser_headers(
    kind: str = "desktop",
    referer: Optional[str] = None,
    accept: str = "html",
    extra: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """Build a consistent browser-like header set.

    Args:
        kind: ``desktop`` or ``mobile``.
        referer: Optional Referer (and Origin for JSON requests).
        accept: ``html`` for documents, ``json`` for XHR-style API calls.
        extra: Extra headers merged last.
    """
    if kind == "mobile":
        headers = {"User-Agent": mobile_ua()}
    else:
        ua = desktop_ua()
        headers = {"User-Agent": ua}
        match = re.search(r"Chrome/(\d+)", ua)
        if match:
            major = match.group(1)
            platform = '"macOS"' if "Macintosh" in ua else '"Windows"'
            headers.update({
                "Sec-Ch-Ua": f'"Chromium";v="{major}", "Google Chrome";v="{major}", "Not.A/Brand";v="99"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": platform,
            })
    if accept == "json":
        headers["Accept"] = "application/json, text/plain, */*"
    else:
        headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    headers["Accept-Language"] = "zh-CN,zh;q=0.9,en;q=0.8"
    headers["Accept-Encoding"] = "gzip, deflate"
    if referer:
        headers["Referer"] = referer
        if accept == "json":
            parts = urlsplit(referer)
            if parts.scheme and parts.netloc:
                headers["Origin"] = f"{parts.scheme}://{parts.netloc}"
    if extra:
        headers.update(extra)
    return headers


def _redact_url(url: str) -> str:
    """Redact credentials from URLs before debug logging."""
    try:
        parts = urlsplit(url)
        query = []
        for key, value in parse_qsl(parts.query, keep_blank_values=True):
            if any(marker in key.lower() for marker in SECRET_QUERY_KEYS):
                query.append((key, "***"))
            else:
                query.append((key, value))
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
    except Exception:
        return url


def _compute_delay(attempt: int, *, base: float = RETRY_BACKOFF, cap: float = RETRY_CAP) -> float:
    """Compute capped exponential backoff with a small jitter."""
    exponential = base * (2 ** attempt)
    jitter = random.uniform(0, min(base, 1.0))
    return min(cap, exponential + jitter)


def _parse_retry_after(value: Optional[str]) -> Optional[float]:
    """Parse Retry-After seconds or HTTP-date values, capped for CLI use."""
    if not value:
        return None
    try:
        seconds = float(value)
        return max(0.0, min(RETRY_AFTER_CAP, seconds))
    except (TypeError, ValueError):
        pass

    try:
        retry_at = parsedate_to_datetime(value)
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)
        seconds = (retry_at - datetime.now(timezone.utc)).total_seconds()
        return max(0.0, min(RETRY_AFTER_CAP, seconds))
    except (TypeError, ValueError, IndexError, OverflowError):
        return None


def _decode_body(raw: bytes, headers: Any) -> str:
    """Decompress and decode a response body using its headers."""
    encoding = ""
    content_type = ""
    try:
        encoding = (headers.get("Content-Encoding") or "").lower()
        content_type = headers.get("Content-Type") or ""
    except Exception:
        pass
    if encoding == "gzip" or raw[:2] == b"\x1f\x8b":
        try:
            raw = gzip.decompress(raw)
        except OSError:
            pass
    elif encoding == "deflate":
        try:
            raw = zlib.decompress(raw)
        except zlib.error:
            try:
                raw = zlib.decompress(raw, -zlib.MAX_WBITS)
            except zlib.error:
                pass

    charset = "utf-8"
    match = re.search(r"charset=([\w-]+)", content_type, re.I)
    if match:
        charset = match.group(1).lower()
    if charset in ("gbk", "gb2312", "gb18030"):
        charset = "gb18030"
    try:
        return raw.decode(charset, errors="replace")
    except LookupError:
        return raw.decode("utf-8", errors="replace")


def looks_like_antibot(body: str) -> bool:
    """Heuristic: short interstitial pages with captcha/visitor markers."""
    if not body:
        return True
    head = body[:6000]
    return any(marker in head for marker in ANTIBOT_MARKERS)


def _open(req: urllib.request.Request, timeout: int, opener=None):
    if opener is not None:
        return opener.open(req, timeout=timeout)
    return urllib.request.urlopen(req, timeout=timeout)


def _send(
    req: urllib.request.Request,
    *,
    timeout: int,
    retries: int,
    backoff: float,
    opener=None,
) -> Tuple[int, str, str]:
    """Send a request with the shared retry policy.

    Returns (status, final_url, decoded_body). Raises HTTPError.
    """
    log(f"{req.get_method()} {_redact_url(req.full_url)}")
    last_error: Optional[HTTPError] = None
    attempts = max(1, retries)
    for attempt in range(attempts):
        try:
            with _open(req, timeout, opener) as response:
                raw = response.read()
                headers = getattr(response, "headers", {}) or {}
                body = _decode_body(raw, headers)
                status = getattr(response, "status", 200)
                final_url = response.geturl() if hasattr(response, "geturl") else req.full_url
                log(f"Response: {status} ({len(body)} chars)")
                return status, final_url, body
        except urllib.error.HTTPError as e:
            body = None
            try:
                body = _decode_body(e.read(), getattr(e, "headers", {}) or {})
            except Exception:
                pass
            log(f"HTTP Error {e.code}: {e.reason}")
            if body:
                log(f"Error body: {' '.join(body.split())[:200]}")
            if e.code == 412:
                last_error = HTTPError(
                    "HTTP 412: 请求被平台 WAF/风控拦截（Precondition Failed）",
                    412,
                    body,
                )
            else:
                last_error = HTTPError(f"HTTP {e.code}: {e.reason}", e.code, body)

            # Don't retry client errors (4xx) except rate limits.
            if 400 <= e.code < 500 and e.code != 429:
                raise last_error

            if attempt < attempts - 1:
                retry_after = e.headers.get("Retry-After") if getattr(e, "headers", None) else None
                delay = _parse_retry_after(retry_after) if e.code == 429 else None
                if delay is None:
                    delay = _compute_delay(attempt, base=backoff)
                if e.code == 429:
                    log(f"Rate limited (429). Waiting {delay:.1f}s before retry {attempt + 2}/{attempts}")
                time.sleep(delay)
        except urllib.error.URLError as e:
            log(f"URL Error: {e.reason}")
            last_error = HTTPError(f"URL Error: {e.reason}")
            if attempt < attempts - 1:
                time.sleep(_compute_delay(attempt, base=backoff))
        except (OSError, TimeoutError, ConnectionResetError) as e:
            log(f"Connection error: {type(e).__name__}: {e}")
            last_error = HTTPError(f"Connection error: {type(e).__name__}: {e}")
            if attempt < attempts - 1:
                time.sleep(_compute_delay(attempt, base=backoff))

    if last_error:
        raise last_error
    raise HTTPError("Request failed with no error details")


def request(
    method: str,
    url: str,
    headers: Optional[Dict[str, str]] = None,
    json_data: Optional[Dict[str, Any]] = None,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = MAX_RETRIES,
    backoff: float = RETRY_BACKOFF,
    raw: bool = False,
    data: Optional[bytes] = None,
    opener=None,
) -> Any:
    """Make an HTTP request and return the parsed JSON (or text when raw=True).

    Args:
        method: HTTP method (GET, POST, etc.)
        url: Request URL
        headers: Optional headers dict
        json_data: Optional JSON body (for POST)
        timeout: Request timeout in seconds
        retries: Total attempts (1 disables retry)
        backoff: Exponential backoff base factor in seconds
        raw: If True, return raw text instead of parsed JSON
        data: Optional pre-encoded body (form posts)
        opener: Optional urllib opener (cookie sessions)

    Raises:
        HTTPError: On request failure or invalid JSON
    """
    headers = dict(headers or {})
    headers.setdefault("User-Agent", USER_AGENT)

    body_bytes = data
    if json_data is not None:
        body_bytes = json.dumps(json_data).encode("utf-8")
        headers.setdefault("Content-Type", "application/json")

    req = urllib.request.Request(url, data=body_bytes, headers=headers, method=method)
    _status, _final_url, body = _send(req, timeout=timeout, retries=retries, backoff=backoff, opener=opener)
    if raw:
        return body
    try:
        return json.loads(body) if body else {}
    except json.JSONDecodeError as e:
        log(f"JSON decode error: {e}")
        raise HTTPError(f"Invalid JSON response: {e}", body=body[:500] if body else None)


def get(url: str, headers: Optional[Dict[str, str]] = None, **kwargs) -> Dict[str, Any]:
    """Make a GET request and parse JSON."""
    return request("GET", url, headers=headers, **kwargs)


def post(url: str, json_data: Dict[str, Any], headers: Optional[Dict[str, str]] = None, **kwargs) -> Dict[str, Any]:
    """Make a POST request with JSON body."""
    return request("POST", url, headers=headers, json_data=json_data, **kwargs)


def post_raw(url: str, json_data: Dict[str, Any], headers: Optional[Dict[str, str]] = None, **kwargs) -> str:
    """Make a POST request with JSON body and return raw text."""
    return request("POST", url, headers=headers, json_data=json_data, raw=True, **kwargs)


def get_text(url: str, headers: Optional[Dict[str, str]] = None, **kwargs) -> str:
    """GET a page and return decoded text (gzip + charset aware)."""
    kwargs.setdefault("retries", 1)
    return request("GET", url, headers=headers, raw=True, **kwargs)


def fetch(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    *,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = 1,
    opener=None,
) -> Tuple[int, str, str]:
    """GET ``url`` and return ``(status, final_url, text)``.

    Unlike :func:`get_text` this exposes the post-redirect URL, which callers
    use to detect "redirected to homepage/login" responses.
    """
    merged = dict(headers or {})
    merged.setdefault("User-Agent", USER_AGENT)
    req = urllib.request.Request(url, headers=merged, method="GET")
    return _send(req, timeout=timeout, retries=retries, backoff=RETRY_BACKOFF, opener=opener)


class Session:
    """A tiny cookie-keeping HTTP session on top of urllib.

    Platforms such as Bilibili (buvid3) and Weibo (visitor SUB/SUBP) gate
    their public APIs on cookies issued by a previous request.
    """

    def __init__(self, headers: Optional[Dict[str, str]] = None):
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.headers: Dict[str, str] = dict(headers or {})

    def set_cookie(self, name: str, value: str, domain: str, path: str = "/") -> None:
        cookie = http.cookiejar.Cookie(
            version=0, name=name, value=value, port=None, port_specified=False,
            domain=domain, domain_specified=True, domain_initial_dot=domain.startswith("."),
            path=path, path_specified=True, secure=False, expires=None, discard=True,
            comment=None, comment_url=None, rest={}, rfc2109=False,
        )
        self.jar.set_cookie(cookie)

    def load_cookie_header(self, cookie_header: str, domain: str) -> int:
        """Load a browser-copied ``a=1; b=2`` cookie string for a domain."""
        count = 0
        for part in (cookie_header or "").split(";"):
            if "=" not in part:
                continue
            name, _, value = part.strip().partition("=")
            if name:
                self.set_cookie(name.strip(), value.strip(), domain)
                count += 1
        return count

    def cookie_names(self) -> set:
        return {c.name for c in self.jar}

    def get_cookie(self, name: str) -> Optional[str]:
        for cookie in self.jar:
            if cookie.name == name:
                return cookie.value
        return None

    def _headers(self, headers: Optional[Dict[str, str]]) -> Dict[str, str]:
        merged = dict(self.headers)
        if headers:
            merged.update(headers)
        return merged

    def request(self, method: str, url: str, headers: Optional[Dict[str, str]] = None, **kwargs) -> Any:
        return request(method, url, headers=self._headers(headers), opener=self.opener, **kwargs)

    def get_json(self, url: str, headers: Optional[Dict[str, str]] = None, **kwargs) -> Any:
        kwargs.setdefault("retries", 1)
        return self.request("GET", url, headers=headers, **kwargs)

    def get_text(self, url: str, headers: Optional[Dict[str, str]] = None, **kwargs) -> str:
        kwargs.setdefault("retries", 1)
        return self.request("GET", url, headers=headers, raw=True, **kwargs)

    def post_form(self, url: str, form: Dict[str, Any], headers: Optional[Dict[str, str]] = None, **kwargs) -> str:
        kwargs.setdefault("retries", 1)
        merged = dict(headers or {})
        merged.setdefault("Content-Type", "application/x-www-form-urlencoded")
        data = urllib.parse.urlencode(form).encode("utf-8")
        return self.request("POST", url, headers=merged, data=data, raw=True, **kwargs)
