"""Multi-engine public web search used as the last-resort fallback.

Author: Jesse (https://github.com/Jesseovo)

Why this module exists (v4):
- v3 shipped five copies of a Bing-only ``site:`` fallback. From many regions
  ``cn.bing.com/search`` silently redirects to the Bing homepage, and when
  Bing suspects automation it serves *unrelated* decoy results, which the old
  code happily reported as "知乎/小红书" evidence.
- This module tries several engines (``cn.bing.com`` -> DuckDuckGo HTML ->
  ``www.bing.com``), throttles each engine, remembers engines that answered
  with a challenge/homepage for the rest of the run, unwraps redirect links,
  and *validates* every hit against a platform URL pattern plus a minimum
  topic relevance before accepting it.

Engine order can be overridden with ``LAST30DAYS_WEBSEARCH_ENGINES``
(comma-separated: ``bing_cn,ddg,bing``).
"""

import base64
import html as html_lib
import os
import re
import sys
import threading
import time
import urllib.parse
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Pattern, Sequence, Union

from . import http, relevance

DEFAULT_ENGINES = ("bing_cn", "ddg", "bing")
ENGINES_ENV = "LAST30DAYS_WEBSEARCH_ENGINES"
MIN_INTERVAL_SECONDS = 2.5
DEFAULT_MIN_RELEVANCE = 0.2

_lock = threading.Lock()
_engine_locks: Dict[str, threading.Lock] = {}
_last_request_at: Dict[str, float] = {}
_blocked: Dict[str, str] = {}


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    engine: str
    date: Optional[str] = None


class EngineBlocked(Exception):
    """The engine answered with a challenge, consent page or homepage."""


def reset_state() -> None:
    """Forget throttling/blocked state (tests and long-lived processes)."""
    with _lock:
        _blocked.clear()
        _last_request_at.clear()


def blocked_engines() -> Dict[str, str]:
    with _lock:
        return dict(_blocked)


def configured_engines() -> List[str]:
    raw = os.environ.get(ENGINES_ENV, "").strip()
    if not raw:
        return list(DEFAULT_ENGINES)
    names = [part.strip().lower() for part in raw.split(",") if part.strip()]
    return [name for name in names if name in _ENGINE_FUNCS] or list(DEFAULT_ENGINES)


def _engine_lock(engine: str) -> threading.Lock:
    with _lock:
        lock = _engine_locks.get(engine)
        if lock is None:
            lock = threading.Lock()
            _engine_locks[engine] = lock
        return lock


def _throttle(engine: str) -> None:
    last = _last_request_at.get(engine)
    if last is not None:
        wait = MIN_INTERVAL_SECONDS - (time.monotonic() - last)
        if wait > 0:
            time.sleep(wait)
    _last_request_at[engine] = time.monotonic()


def clean_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text or "")
    text = html_lib.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


_CN_DATE_RE = re.compile(r"(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日")
_ISO_DATE_RE = re.compile(r"(20\d{2})-(\d{1,2})-(\d{1,2})")


def extract_date(text: str) -> Optional[str]:
    """Find a leading ``2026年5月30日`` / ``2026-05-30`` date in a snippet."""
    if not text:
        return None
    match = _CN_DATE_RE.search(text[:40]) or _ISO_DATE_RE.search(text[:40])
    if not match:
        return None
    year, month, day = (int(g) for g in match.groups())
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return None
    return f"{year:04d}-{month:02d}-{day:02d}"


def unwrap_bing_url(href: str) -> str:
    """Decode ``bing.com/ck/a?...&u=a1<base64url>`` redirect links."""
    href = html_lib.unescape(href or "")
    if "bing.com/ck/a" not in href:
        return href
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(href).query)
    encoded = (query.get("u") or [""])[0]
    if not encoded.startswith("a1"):
        return href
    payload = encoded[2:]
    payload += "=" * (-len(payload) % 4)
    try:
        return base64.urlsafe_b64decode(payload).decode("utf-8", "replace")
    except (ValueError, TypeError):
        return href


def unwrap_ddg_url(href: str) -> str:
    """Decode ``//duckduckgo.com/l/?uddg=<url>`` redirect links."""
    href = html_lib.unescape(href or "")
    if "duckduckgo.com/l/" not in href:
        return href
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(href).query)
    target = (query.get("uddg") or [""])[0]
    return target or href


def parse_bing_html(body: str, engine: str = "bing") -> List[SearchResult]:
    """Parse Bing SERP HTML (both cn.bing.com and www.bing.com)."""
    results: List[SearchResult] = []
    for block in re.findall(r'<li class="b_algo"[^>]*>([\s\S]*?)</li>', body or ""):
        title_match = re.search(r'<h2[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>([\s\S]*?)</a>', block)
        if not title_match:
            continue
        url = unwrap_bing_url(title_match.group(1))
        title = clean_text(title_match.group(2))
        snippet_match = (
            re.search(r'<p[^>]*class="[^"]*b_lineclamp[^"]*"[^>]*>([\s\S]*?)</p>', block)
            or re.search(r'<div class="b_caption"[^>]*>[\s\S]*?<p[^>]*>([\s\S]*?)</p>', block)
            or re.search(r"<p[^>]*>([\s\S]*?)</p>", block)
        )
        snippet = clean_text(snippet_match.group(1)) if snippet_match else ""
        date_match = re.search(r'<span class="news_dt">([^<]+)</span>', block)
        date = extract_date(clean_text(date_match.group(1))) if date_match else extract_date(snippet)
        if url.startswith("http") and title:
            results.append(SearchResult(title=title, url=url, snippet=snippet, engine=engine, date=date))
    return results


def parse_ddg_html(body: str) -> List[SearchResult]:
    """Parse DuckDuckGo's no-JS HTML results page."""
    results: List[SearchResult] = []
    anchors = list(re.finditer(r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>([\s\S]*?)</a>', body or ""))
    snippets = re.findall(r'<a[^>]*class="result__snippet"[^>]*>([\s\S]*?)</a>', body or "")
    for idx, match in enumerate(anchors):
        url = unwrap_ddg_url(match.group(1))
        if url.startswith("//"):
            url = "https:" + url
        title = clean_text(match.group(2))
        snippet = clean_text(snippets[idx]) if idx < len(snippets) else ""
        if url.startswith("http") and title:
            results.append(SearchResult(title=title, url=url, snippet=snippet, engine="ddg", date=extract_date(snippet)))
    return results


def _is_bing_homepage(final_url: str, body: str) -> bool:
    parts = urllib.parse.urlsplit(final_url or "")
    if parts.path in ("", "/") and "b_algo" not in (body or ""):
        return True
    return 'class="hp_body' in (body or "") and "b_algo" not in (body or "")


def _search_bing(query: str, *, cn: bool, timeout: int) -> List[SearchResult]:
    host = "cn.bing.com" if cn else "www.bing.com"
    params = {"q": query}
    if cn:
        params["ensearch"] = "0"
    else:
        params["setlang"] = "zh-Hans"
    url = f"https://{host}/search?{urllib.parse.urlencode(params)}"
    headers = http.browser_headers(referer=f"https://{host}/")
    _status, final_url, body = http.fetch(url, headers=headers, timeout=timeout)
    if _is_bing_homepage(final_url, body):
        raise EngineBlocked("重定向到首页（当前网络不返回结果）")
    if http.looks_like_antibot(body) and "b_algo" not in body:
        raise EngineBlocked("返回验证页")
    return parse_bing_html(body, engine="bing_cn" if cn else "bing")


def _search_ddg(query: str, *, timeout: int) -> List[SearchResult]:
    url = f"https://html.duckduckgo.com/html/?{urllib.parse.urlencode({'q': query, 'kl': 'cn-zh'})}"
    headers = http.browser_headers(referer="https://html.duckduckgo.com/")
    body = http.get_text(url, headers=headers, timeout=timeout)
    if "anomaly" in body and "result__a" not in body:
        raise EngineBlocked("触发人机验证（请求过于频繁）")
    return parse_ddg_html(body)


_ENGINE_FUNCS: Dict[str, Callable[..., List[SearchResult]]] = {
    "bing_cn": lambda q, timeout: _search_bing(q, cn=True, timeout=timeout),
    "bing": lambda q, timeout: _search_bing(q, cn=False, timeout=timeout),
    "ddg": lambda q, timeout: _search_ddg(q, timeout=timeout),
}


def search(
    query: str,
    *,
    limit: int = 10,
    topic: Optional[str] = None,
    url_pattern: Optional[Union[str, Pattern]] = None,
    min_relevance: float = DEFAULT_MIN_RELEVANCE,
    engines: Optional[Sequence[str]] = None,
    timeout: int = 10,
    label: str = "websearch",
) -> List[SearchResult]:
    """Run ``query`` against the configured engines until enough valid hits.

    Args:
        query: Full query (may include ``site:`` operators).
        limit: Max results to return.
        topic: Topic used for the relevance gate (defaults to ``query``).
        url_pattern: Regex every accepted URL must match (platform guard).
        min_relevance: Minimum token-overlap relevance of title+snippet.
        engines: Engine names; defaults to ``configured_engines()``.
        timeout: Per-request timeout.
        label: Log prefix.
    """
    pattern = re.compile(url_pattern) if isinstance(url_pattern, str) else url_pattern
    gate_topic = topic or re.sub(r"site:\S+", " ", query).strip()
    accepted: List[SearchResult] = []
    seen = set()

    for engine in (engines or configured_engines()):
        func = _ENGINE_FUNCS.get(engine)
        if func is None:
            continue
        with _lock:
            if engine in _blocked:
                continue
        try:
            with _engine_lock(engine):
                _throttle(engine)
                raw_results = func(query, timeout)
        except EngineBlocked as exc:
            with _lock:
                _blocked[engine] = str(exc)
            http.log(f"[{label}] {engine} blocked: {exc}")
            continue
        except Exception as exc:  # network errors: try the next engine
            http.log(f"[{label}] {engine} failed: {type(exc).__name__}: {exc}")
            continue

        for result in raw_results:
            key = result.url.split("#", 1)[0]
            if key in seen:
                continue
            if pattern is not None and not pattern.search(result.url):
                continue
            if min_relevance > 0 and gate_topic:
                rel = relevance.token_overlap_relevance(gate_topic, f"{result.title} {result.snippet}")
                if rel < min_relevance:
                    continue
            seen.add(key)
            accepted.append(result)
            if len(accepted) >= limit:
                return accepted
        if accepted:
            # One engine produced validated hits; don't hammer the others.
            break
    return accepted


def site_search(
    sites: Union[str, Sequence[str]],
    topic: str,
    *,
    limit: int = 10,
    url_pattern: Optional[Union[str, Pattern]] = None,
    min_relevance: float = DEFAULT_MIN_RELEVANCE,
    label: str = "websearch",
) -> List[SearchResult]:
    """Search ``site:<domain> topic`` with validation (see :func:`search`)."""
    if isinstance(sites, str):
        sites = [sites]
    site_expr = " OR ".join(f"site:{site}" for site in sites)
    query = f"{site_expr} {topic}".strip()
    return search(
        query,
        limit=limit,
        topic=topic,
        url_pattern=url_pattern,
        min_relevance=min_relevance,
        label=label,
    )


_ENGINE_NAMES = {"bing_cn": "cn.bing.com", "bing": "www.bing.com", "ddg": "DuckDuckGo"}


def describe_failure(label: str) -> str:
    """Human-readable reason when the web-search fallback produced nothing."""
    blocked = blocked_engines()
    engines = "、".join(_ENGINE_NAMES.get(e, e) for e in configured_engines())
    if not blocked:
        return f"公开搜索兜底（{engines}）没有找到可验证的{label}链接"
    reasons = "；".join(f"{_ENGINE_NAMES.get(name, name)} {why}" for name, why in blocked.items())
    return f"公开搜索兜底没有找到可验证的{label}链接（{reasons}）"


def warn(label: str, message: str) -> None:
    sys.stderr.write(f"[{label}] {message}\n")
