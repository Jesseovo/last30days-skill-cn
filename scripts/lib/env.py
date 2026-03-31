"""Environment and API key management for last30days-cn (Chinese platforms).

Author: Jesse (https://github.com/ChiTing111)
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

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


def _check_file_permissions(path: Path) -> None:
    try:
        mode = path.stat().st_mode
        if mode & 0o044:
            import sys
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

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                if value and value[0] in ('"', "'") and value[-1] == value[0]:
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


def get_config() -> Dict[str, Any]:
    """Load configuration: os.environ overrides project .env overrides global .env.

    Only Chinese-platform keys are populated.
    """
    file_env = load_env_file(CONFIG_FILE) if CONFIG_FILE else {}
    project_env_path = _find_project_env()
    project_env = load_env_file(project_env_path) if project_env_path else {}
    merged_env = {**file_env, **project_env}

    keys = [
        ("WEIBO_ACCESS_TOKEN", None),
        ("SCRAPECREATORS_API_KEY", None),
        ("ZHIHU_COOKIE", None),
        ("TIKHUB_API_KEY", None),
        ("DOUYIN_API_KEY", None),
        ("WECHAT_API_KEY", None),
        ("BAIDU_API_KEY", None),
        ("BAIDU_SECRET_KEY", None),
        ("TOUTIAO_API_KEY", None),
        ("XIAOHONGSHU_API_BASE", None),
        ("SETUP_COMPLETE", None),
    ]

    config: Dict[str, Any] = {}
    for key, default in keys:
        config[key] = os.environ.get(key) or merged_env.get(key, default)

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


def get_xiaohongshu_api_base(config: Dict[str, Any]) -> str:
    """Xiaohongshu HTTP API base URL (trailing slash stripped)."""
    return (config.get("XIAOHONGSHU_API_BASE") or "http://host.docker.internal:18060").rstrip("/")


def is_weibo_available(config: Dict[str, Any]) -> bool:
    return bool(config.get("WEIBO_ACCESS_TOKEN"))


def is_xiaohongshu_available(config: Dict[str, Any]) -> bool:
    from . import http

    base = get_xiaohongshu_api_base(config)
    try:
        health = http.get(f"{base}/health", timeout=3, retries=2)
        if not isinstance(health, dict) or not health.get("success"):
            return False
        login = http.get(f"{base}/api/v1/login/status", timeout=8, retries=2)
        is_logged_in = (
            login.get("data", {}).get("is_logged_in")
            if isinstance(login, dict) else False
        )
        return bool(is_logged_in)
    except Exception:
        return False


def is_bilibili_available() -> bool:
    return True


def is_zhihu_available() -> bool:
    return True


def is_douyin_available(config: Dict[str, Any]) -> bool:
    return bool(config.get("TIKHUB_API_KEY") or config.get("DOUYIN_API_KEY"))


def is_wechat_available(config: Dict[str, Any]) -> bool:
    return bool(config.get("WECHAT_API_KEY"))


def is_baidu_api_available(config: Dict[str, Any]) -> bool:
    return bool(config.get("BAIDU_API_KEY") and config.get("BAIDU_SECRET_KEY"))


def is_toutiao_available() -> bool:
    return True


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
    """What is still missing for optional (non–public) sources.

    Returns ``'none'`` when at least one extension credential is set. Otherwise returns a
    Chinese summary of unset env keys (not equal to ``'none'``, so legacy English NUX in
    ``ui.show_promo`` does not fire for the CN build).
    """
    if (
        is_weibo_available(config)
        or is_douyin_available(config)
        or is_wechat_available(config)
        or is_baidu_api_available(config)
        or bool(config.get("SCRAPECREATORS_API_KEY"))
        or bool(config.get("ZHIHU_COOKIE"))
        or bool(config.get("TOUTIAO_API_KEY"))
    ):
        return "none"
    lines: List[str] = []
    if not config.get("WEIBO_ACCESS_TOKEN"):
        lines.append("WEIBO_ACCESS_TOKEN（微博）")
    if not config.get("SCRAPECREATORS_API_KEY"):
        lines.append("SCRAPECREATORS_API_KEY")
    if not config.get("ZHIHU_COOKIE"):
        lines.append("ZHIHU_COOKIE")
    if not (config.get("TIKHUB_API_KEY") or config.get("DOUYIN_API_KEY")):
        lines.append("TIKHUB_API_KEY 或 DOUYIN_API_KEY")
    if not config.get("WECHAT_API_KEY"):
        lines.append("WECHAT_API_KEY")
    if not (config.get("BAIDU_API_KEY") and config.get("BAIDU_SECRET_KEY")):
        lines.append("BAIDU_API_KEY + BAIDU_SECRET_KEY")
    if not config.get("TOUTIAO_API_KEY"):
        lines.append("TOUTIAO_API_KEY")
    return "未配置：" + "；".join(lines)


def _parse_available(available: str) -> Set[str]:
    if not available or available == "none":
        return set()
    return {x.strip() for x in available.split(",") if x.strip()}


def validate_sources(
    requested: str,
    available: str,
    include_web: bool = False,
) -> tuple[str, Optional[str]]:
    """Validate requested sources against ``get_available_sources`` output.

    * ``requested`` — ``'auto'``, ``'all'``, or comma-separated source ids
      (e.g. ``weibo,bilibili``).
    * ``available`` — comma-separated ids from :func:`get_available_sources`.
    * ``include_web`` — when True and ``baidu`` is available, ensures ``baidu``
      is included for ``auto`` / ``all``.

    Returns:
        ``(effective_csv, error_message)`` — ``error_message`` is None on success.
    """
    avail = _parse_available(available)
    if not avail:
        return "none", "没有可用的数据源。"

    legacy_auto = {"auto", "all"}
    req = requested.strip().lower()
    if req in legacy_auto or req == "":
        chosen = set(avail)
        if include_web and "baidu" in avail:
            chosen.add("baidu")
        return ",".join(sorted(chosen)), None

    if req == "all":
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
