"""Environment and API key management for last30days-cn.

Author: Jesse (https://github.com/Jesseovo)

Priority: process environment > project ``.claude/last30days-cn.env`` >
global ``~/.config/last30days-cn/.env``.

v4:
- Runtime switches written in the .env files (``LAST30DAYS_DISABLE_BROWSER``,
  ``LAST30DAYS_BROWSER_PATH``, ``EXCLUDE_SOURCES``, ``INCLUDE_SOURCES`` ...)
  are now honoured; v3 only read them from the real process environment.
- New optional keys: ``WEIBO_COOKIE``, ``BILIBILI_COOKIE``, ``GITHUB_TOKEN``.
- xiaohongshu-mcp is used when ``XIAOHONGSHU_API_BASE`` is set, or when a
  local server answers on 127.0.0.1:18060 (v3 always tried
  host.docker.internal and reported it as "configured").
- Python 3.8 compatible (v3 used ``tuple[...]`` at runtime and crashed on 3.8).
"""

import json
import logging
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# Legacy: empty registry so optional imports (e.g. setup_wizard) do not break.
COOKIE_DOMAINS: Dict[str, Dict[str, Any]] = {}

_config_override = os.environ.get("LAST30DAYS_CN_CONFIG_DIR") or os.environ.get("LAST30DAYS_CONFIG_DIR")
if _config_override == "":
    CONFIG_DIR = None
    CONFIG_FILE = None
elif _config_override:
    CONFIG_DIR = Path(_config_override)
    CONFIG_FILE = CONFIG_DIR / ".env"
else:
    CONFIG_DIR = Path.home() / ".config" / "last30days-cn"
    CONFIG_FILE = CONFIG_DIR / ".env"

CONFIG_KEYS = (
    "WEIBO_ACCESS_TOKEN",
    "WEIBO_COOKIE",
    "SCRAPECREATORS_API_KEY",
    "ZHIHU_COOKIE",
    "BILIBILI_COOKIE",
    "TIKHUB_API_KEY",
    "DOUYIN_API_KEY",
    "WECHAT_API_KEY",
    "BAIDU_API_KEY",
    "BAIDU_SECRET_KEY",
    "TOUTIAO_API_KEY",
    "XIAOHONGSHU_API_BASE",
    "GITHUB_TOKEN",
    "SETUP_COMPLETE",
)

# Non-secret runtime switches that may live in the .env files.
RUNTIME_SETTINGS = (
    "LAST30DAYS_DEFAULT_SEARCH",
    "EXCLUDE_SOURCES",
    "INCLUDE_SOURCES",
    "LAST30DAYS_DISABLE_BROWSER",
    "LAST30DAYS_BROWSER_PATH",
    "LAST30DAYS_BROWSER_CHANNEL",
    "LAST30DAYS_BROWSER_CONCURRENCY",
    "LAST30DAYS_WEBSEARCH_ENGINES",
    "LAST30DAYS_USER_AGENT",
    "LAST30DAYS_OUTPUT_DIR",
    "LAST30DAYS_CACHE_DIR",
    "LAST30DAYS_UPSTREAM",
    "LAST30DAYS_UPSTREAM_PYTHON",
    "LAST30DAYS_UPSTREAM_SEARCH",
    "LAST30DAYS_HOT_SOURCES",
    "LAST30DAYS_HOT_FEEDS",
)

DEFAULT_XHS_MCP_CANDIDATES = ("http://127.0.0.1:18060",)


def _check_file_permissions(path: Path) -> None:
    if os.name == "nt":
        return
    try:
        mode = path.stat().st_mode
        if mode & 0o044:
            sys.stderr.write(
                f"[last30days-cn] WARNING: {path} is readable by other users. "
                f"Run: chmod 600 {path}\n"
            )
            sys.stderr.flush()
    except OSError:
        pass


def load_env_file(path: Path) -> Dict[str, str]:
    """Load environment variables from a file."""
    env: Dict[str, str] = {}
    if not path or not path.exists():
        return env
    _check_file_permissions(path)

    with open(path, "r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export "):].strip()
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                if value and value[0] in ('"', "'") and value[-1] == value[0] and len(value) >= 2:
                    value = value[1:-1]
                if key and value:
                    env[key] = value
    return env


def _find_project_env() -> Optional[Path]:
    """Find per-project .env by walking up from cwd."""
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        candidate = parent / ".claude" / "last30days-cn.env"
        if candidate.exists():
            return candidate
        if parent == Path.home() or parent == parent.parent:
            break
    return None


def apply_runtime_settings(file_env: Dict[str, str]) -> List[str]:
    """Export non-secret runtime switches from .env files into os.environ.

    The real process environment always wins. Returns the keys applied.
    """
    applied = []
    for key in RUNTIME_SETTINGS:
        if key in file_env and not os.environ.get(key):
            os.environ[key] = file_env[key]
            applied.append(key)
    return applied


def get_config() -> Dict[str, Any]:
    """Load configuration: os.environ overrides project .env overrides global .env."""
    file_env = load_env_file(CONFIG_FILE) if CONFIG_FILE else {}
    project_env_path = _find_project_env()
    project_env = load_env_file(project_env_path) if project_env_path else {}
    merged_env = {**file_env, **project_env}
    apply_runtime_settings(merged_env)

    config: Dict[str, Any] = {}
    for key in CONFIG_KEYS:
        config[key] = os.environ.get(key) or merged_env.get(key)

    if project_env_path:
        config["_CONFIG_SOURCE"] = f"project:{project_env_path}"
    elif CONFIG_FILE and CONFIG_FILE.exists():
        config["_CONFIG_SOURCE"] = f"global:{CONFIG_FILE}"
    else:
        config["_CONFIG_SOURCE"] = "env_only"

    return config


def config_exists() -> bool:
    """True if project or global config file exists."""
    if _find_project_env():
        return True
    if CONFIG_FILE:
        return CONFIG_FILE.exists()
    return False


def get_xiaohongshu_api_base(config: Dict[str, Any]) -> Optional[str]:
    """Configured xiaohongshu-mcp base URL (trailing slash stripped), or None."""
    base = (config.get("XIAOHONGSHU_API_BASE") or "").strip()
    return base.rstrip("/") or None


_xhs_mcp_probe: Dict[str, Optional[str]] = {}


def discover_xiaohongshu_mcp(config: Dict[str, Any], timeout: float = 1.5) -> Optional[str]:
    """Configured MCP base, else a local xiaohongshu-mcp that answers /health."""
    configured = get_xiaohongshu_api_base(config)
    if configured:
        return configured
    if "result" in _xhs_mcp_probe:
        return _xhs_mcp_probe["result"]
    found = None
    for base in DEFAULT_XHS_MCP_CANDIDATES:
        try:
            with urllib.request.urlopen(f"{base}/health", timeout=timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8", "replace") or "{}")
            if isinstance(payload, dict) and (payload.get("success") or payload.get("status") == "ok"):
                found = base
                break
        except Exception:
            continue
    _xhs_mcp_probe["result"] = found
    return found


def is_weibo_available(config: Dict[str, Any]) -> bool:
    """True when a credentialed Weibo search path exists (token / cookie / browser login)."""
    if config.get("WEIBO_ACCESS_TOKEN") or config.get("WEIBO_COOKIE"):
        return True
    try:
        from . import crawler_bridge
        return crawler_bridge.is_playwright_available() and crawler_bridge.has_login("weibo")
    except Exception:
        return False


def is_xiaohongshu_available(config: Dict[str, Any]) -> bool:
    """Xiaohongshu can always be *attempted* (public-search fallback exists)."""
    return True


def xiaohongshu_paths(config: Dict[str, Any]) -> Dict[str, bool]:
    """Which XHS paths are usable right now (for --diagnose)."""
    mcp_ok = False
    base = discover_xiaohongshu_mcp(config)
    if base:
        from . import http
        try:
            login = http.get(f"{base}/api/v1/login/status", timeout=4, retries=1)
            mcp_ok = bool(isinstance(login, dict) and (login.get("data") or {}).get("is_logged_in"))
        except Exception:
            mcp_ok = False
    browser = False
    logged_in = False
    try:
        from . import crawler_bridge
        browser = crawler_bridge.is_playwright_available()
        logged_in = crawler_bridge.has_login("xiaohongshu")
    except Exception:
        pass
    return {"mcp": mcp_ok, "browser": browser, "browser_logged_in": logged_in, "site_search": True}


def is_bilibili_available() -> bool:
    return True


def is_zhihu_available() -> bool:
    return True


def is_douyin_available(config: Dict[str, Any]) -> bool:
    if config.get("TIKHUB_API_KEY") or config.get("DOUYIN_API_KEY"):
        return True
    try:
        from . import crawler_bridge
        return crawler_bridge.is_playwright_available()
    except Exception:
        return False


def is_wechat_available(config: Dict[str, Any]) -> bool:
    return bool(config.get("WECHAT_API_KEY"))


def is_baidu_api_available(config: Dict[str, Any]) -> bool:
    """千帆 AI 搜索只需要 BAIDU_API_KEY（BAIDU_SECRET_KEY 已不再需要）。"""
    return bool(config.get("BAIDU_API_KEY"))


def is_toutiao_available() -> bool:
    return True


# ---------------------------------------------------------------------------
# 实时探测（仅供 --diagnose 使用）
#
# is_*_available() 反映的是"配置/能力是否具备"；下面的 probe_* 则真实发一个
# 短超时请求，反映各源公开端点此刻是否还能拿到数据。约定：
#   - 端点返回明确错误（HTTP 4xx/5xx）或空数据 → False（诚实标记为不可用）
#   - 仅连接超时/网络异常 → fail-open 返回 True（瞬时故障不武断判死）
# ---------------------------------------------------------------------------


def _probe(fn) -> bool:
    from . import http
    try:
        return bool(fn())
    except http.HTTPError as exc:
        if exc.status_code is None:
            return True  # network hiccup: fail open
        return False
    except urllib.error.HTTPError:
        return False
    except Exception:
        return True


def probe_bilibili(timeout: int = 8) -> bool:
    """探测 B站 WBI 搜索是否返回结果（与 bilibili.search_bilibili 同一路径）。"""
    from . import bilibili

    def run():
        return bilibili._search_page("AI", 1)

    return _probe(run)


def probe_zhihu(timeout: int = 5) -> bool:
    """知乎匿名搜索接口探测（v4：匿名请求恒失败，仅在配置 Cookie 时有意义）。"""
    from . import http, zhihu
    cookie = os.environ.get("ZHIHU_COOKIE")

    def run():
        headers = http.browser_headers(referer="https://www.zhihu.com/search", accept="json")
        if cookie:
            headers["Cookie"] = cookie
        data = http.get(f"{zhihu.SEARCH_URL}?t=general&q=AI&offset=0&limit=1", headers=headers, timeout=timeout, retries=1)
        return bool((data or {}).get("data"))

    return _probe(run)


def probe_toutiao(timeout: int = 10) -> bool:
    """探测头条资讯搜索（so.toutiao.com 服务端渲染页）是否返回结果卡片。"""
    from . import toutiao

    def run():
        return toutiao._search_via_so("AI", 0)

    return _probe(run)


def probe_weibo_hot(timeout: int = 6) -> bool:
    from . import weibo
    return _probe(lambda: weibo.fetch_hot(5))


def probe_wechat(timeout: int = 10) -> bool:
    from . import wechat
    return _probe(lambda: wechat._search_via_sogou("AI", 1))


def _all_source_ids() -> List[str]:
    return [
        "weibo",
        "xiaohongshu",
        "bilibili",
        "zhihu",
        "douyin",
        "wechat",
        "baidu",
        "toutiao",
    ]


def get_available_sources(config: Dict[str, Any]) -> str:
    """Comma-separated list of source ids that are available for this config."""
    available: List[str] = []
    if is_weibo_available(config):
        available.append("weibo")
    if is_xiaohongshu_available(config):
        available.append("xiaohongshu")
    if is_bilibili_available():
        available.append("bilibili")
    if is_zhihu_available():
        available.append("zhihu")
    if is_douyin_available(config):
        available.append("douyin")
    if is_wechat_available(config):
        available.append("wechat")
    if is_baidu_api_available(config):
        available.append("baidu")
    if is_toutiao_available():
        available.append("toutiao")
    return ",".join(available) if available else "none"


def get_missing_keys(config: Dict[str, Any]) -> str:
    """What is still missing for optional (non-public) sources."""
    if (
        is_weibo_available(config)
        or is_douyin_available(config)
        or is_wechat_available(config)
        or is_baidu_api_available(config)
        or bool(config.get("ZHIHU_COOKIE"))
    ):
        return "none"
    lines: List[str] = []
    if not (config.get("WEIBO_ACCESS_TOKEN") or config.get("WEIBO_COOKIE")):
        lines.append("WEIBO_COOKIE（微博）")
    if not config.get("ZHIHU_COOKIE"):
        lines.append("ZHIHU_COOKIE")
    if not (config.get("TIKHUB_API_KEY") or config.get("DOUYIN_API_KEY")):
        lines.append("TIKHUB_API_KEY 或 DOUYIN_API_KEY")
    if not config.get("WECHAT_API_KEY"):
        lines.append("WECHAT_API_KEY")
    if not config.get("BAIDU_API_KEY"):
        lines.append("BAIDU_API_KEY")
    return "未配置：" + "；".join(lines)


def _parse_available(available: str) -> Set[str]:
    if not available or available == "none":
        return set()
    return {x.strip() for x in available.split(",") if x.strip()}


def validate_sources(
    requested: str,
    available: str,
    include_web: bool = False,
) -> Tuple[str, Optional[str]]:
    """Validate requested sources against ``get_available_sources`` output.

    Returns:
        ``(effective_csv, error_message)`` — ``error_message`` is None on success.
    """
    avail = _parse_available(available)
    if not avail:
        return "none", "没有可用的数据源。"

    req = requested.strip().lower()
    if req in ("auto", "all", ""):
        chosen = set(avail)
        if include_web and "baidu" in avail:
            chosen.add("baidu")
        return ",".join(sorted(chosen)), None

    requested_ids = {x.strip().lower() for x in requested.split(",") if x.strip()}
    valid = set(_all_source_ids())
    unknown = requested_ids - valid
    if unknown:
        return "none", f"未知来源：{', '.join(sorted(unknown))}"

    missing = requested_ids - avail
    if missing:
        return "none", f"以下来源当前不可用：{', '.join(sorted(missing))}"

    return ",".join(sorted(requested_ids)), None
