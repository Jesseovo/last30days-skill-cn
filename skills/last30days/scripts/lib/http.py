"""HTTP utilities for last30days skill (stdlib only).

Author: Jesse (https://github.com/Jesseovo)
"""

import json
import os
import random
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .version import VERSION

DEFAULT_TIMEOUT = 30
DEBUG = os.environ.get("LAST30DAYS_DEBUG", "").lower() in ("1", "true", "yes")


def log(msg: str):
    """Log debug message to stderr."""
    if DEBUG:
        sys.stderr.write(f"[DEBUG] {msg}\n")
        sys.stderr.flush()
MAX_RETRIES = 5
RETRY_DELAY = 2.0
RETRY_BACKOFF = 2.0
USER_AGENT = f"last30days-cn/{VERSION} (Research Skill)"
RETRY_CAP = 30.0
RETRY_AFTER_CAP = 60.0
SECRET_QUERY_KEYS = ("key", "token", "secret", "password", "auth")


class HTTPError(Exception):
    """HTTP request error with status code."""
    def __init__(self, message: str, status_code: Optional[int] = None, body: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


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


def request(
    method: str,
    url: str,
    headers: Optional[Dict[str, str]] = None,
    json_data: Optional[Dict[str, Any]] = None,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = MAX_RETRIES,
    backoff: float = RETRY_BACKOFF,
    raw: bool = False,
) -> Any:
    """Make an HTTP request and return JSON response.

    Args:
        method: HTTP method (GET, POST, etc.)
        url: Request URL
        headers: Optional headers dict
        json_data: Optional JSON body (for POST)
        timeout: Request timeout in seconds
        retries: Number of retries on failure (0 disables retry, v2.1+)
        backoff: Exponential backoff base factor in seconds (v2.1+)
        raw: If True, return raw text instead of parsed JSON

    Returns:
        Parsed JSON response (or raw text if raw=True)

    Raises:
        HTTPError: On request failure
    """
    headers = headers or {}
    headers.setdefault("User-Agent", USER_AGENT)

    data = None
    if json_data is not None:
        data = json.dumps(json_data).encode('utf-8')
        headers.setdefault("Content-Type", "application/json")

    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    log(f"{method} {_redact_url(url)}")

    last_error = None
    attempts = max(1, retries)
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                body = response.read().decode('utf-8')
                log(f"Response: {response.status} ({len(body)} bytes)")
                if raw:
                    return body
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as e:
            body = None
            try:
                body = e.read().decode('utf-8')
            except Exception:
                pass
            log(f"HTTP Error {e.code}: {e.reason}")
            if body:
                snippet = " ".join(body.split())
                log(f"Error body: {snippet[:200]}")
            last_error = HTTPError(f"HTTP {e.code}: {e.reason}", e.code, body)

            # Don't retry client errors (4xx) except rate limits
            if 400 <= e.code < 500 and e.code != 429:
                raise last_error

            if attempt < attempts - 1:
                retry_after = e.headers.get("Retry-After") if hasattr(e, 'headers') else None
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
        except json.JSONDecodeError as e:
            log(f"JSON decode error: {e}")
            last_error = HTTPError(f"Invalid JSON response: {e}")
            raise last_error
        except (OSError, TimeoutError, ConnectionResetError) as e:
            # Handle socket-level errors (connection reset, timeout, etc.)
            log(f"Connection error: {type(e).__name__}: {e}")
            last_error = HTTPError(f"Connection error: {type(e).__name__}: {e}")
            if attempt < attempts - 1:
                time.sleep(_compute_delay(attempt, base=backoff))

    if last_error:
        raise last_error
    raise HTTPError("Request failed with no error details")


def get(url: str, headers: Optional[Dict[str, str]] = None, **kwargs) -> Dict[str, Any]:
    """Make a GET request."""
    return request("GET", url, headers=headers, **kwargs)


def post(url: str, json_data: Dict[str, Any], headers: Optional[Dict[str, str]] = None, **kwargs) -> Dict[str, Any]:
    """Make a POST request with JSON body."""
    return request("POST", url, headers=headers, json_data=json_data, **kwargs)


def post_raw(url: str, json_data: Dict[str, Any], headers: Optional[Dict[str, str]] = None, **kwargs) -> str:
    """Make a POST request with JSON body and return raw text."""
    return request("POST", url, headers=headers, json_data=json_data, raw=True, **kwargs)
