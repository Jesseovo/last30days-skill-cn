"""桥接上游 mvanhorn/last30days 引擎（opt-in，issue #9）。

Author: Jesse (https://github.com/Jesseovo)

X / YouTube / TikTok / Instagram 等平台需要各自的 API Key、Cookie 或 yt-dlp，
上游项目已经维护了这些适配器。与其把几十个海外适配器复制进中文版，v4 选择
「桥接」：如果本机已经安装了上游 skill，就以子进程方式调用它的
``--emit json --json-profile raw``，把 ``items_by_source`` 映射进中文报告。

查找顺序：
1. ``LAST30DAYS_UPSTREAM``：上游 ``last30days.py`` 路径或其 skill 目录
2. 常见安装位置（~/.claude/skills、~/.agents/skills、~/.codex/skills、
   Claude Code 插件缓存）

上游要求 Python 3.12+；当前解释器版本不足时可设置 ``LAST30DAYS_UPSTREAM_PYTHON``。
"""

import glob
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import http

UPSTREAM_ENV = "LAST30DAYS_UPSTREAM"
UPSTREAM_PYTHON_ENV = "LAST30DAYS_UPSTREAM_PYTHON"
UPSTREAM_SEARCH_ENV = "LAST30DAYS_UPSTREAM_SEARCH"
DEFAULT_PLATFORMS = ("x", "youtube", "tiktok")
_THIS_SCRIPTS_DIR = Path(__file__).resolve().parents[1]


def _candidate_paths() -> List[Path]:
    home = Path.home()
    paths = [
        home / ".claude" / "skills" / "last30days" / "scripts" / "last30days.py",
        home / ".agents" / "skills" / "last30days" / "scripts" / "last30days.py",
        home / ".codex" / "skills" / "last30days" / "scripts" / "last30days.py",
        home / ".claude" / "plugins" / "marketplaces" / "last30days-skill" / "skills" / "last30days" / "scripts" / "last30days.py",
    ]
    cache_glob = str(home / ".claude" / "plugins" / "cache" / "last30days-skill" / "last30days" / "*")
    for version_dir in sorted(glob.glob(cache_glob), reverse=True):
        paths.append(Path(version_dir) / "skills" / "last30days" / "scripts" / "last30days.py")
        paths.append(Path(version_dir) / "scripts" / "last30days.py")
    return paths


def is_upstream_script(path: Path) -> bool:
    """True for mvanhorn/last30days (not this CN skill)."""
    try:
        resolved = path.resolve()
    except OSError:
        return False
    if not resolved.is_file():
        return False
    if resolved.parent == _THIS_SCRIPTS_DIR:
        return False
    # Upstream ships lib/pipeline.py; the CN skill never has it.
    if not (resolved.parent / "lib" / "pipeline.py").is_file():
        return False
    skill_md = resolved.parent.parent / "SKILL.md"
    if skill_md.is_file():
        head = skill_md.read_text(encoding="utf-8", errors="replace")[:600]
        if "name: last30days-cn" in head:
            return False
    return True


def find_upstream() -> Optional[Path]:
    override = os.environ.get(UPSTREAM_ENV, "").strip()
    if override:
        candidate = Path(override).expanduser()
        if candidate.is_dir():
            for sub in ("scripts/last30days.py", "skills/last30days/scripts/last30days.py", "last30days.py"):
                if (candidate / sub).is_file():
                    candidate = candidate / sub
                    break
        return candidate if is_upstream_script(candidate) else None
    for candidate in _candidate_paths():
        if is_upstream_script(candidate):
            return candidate.resolve()
    return None


def upstream_python() -> Tuple[Optional[str], str]:
    override = os.environ.get(UPSTREAM_PYTHON_ENV, "").strip()
    if override:
        return override, f"{UPSTREAM_PYTHON_ENV}={override}"
    if sys.version_info >= (3, 12):
        return sys.executable, f"当前解释器 Python {sys.version_info.major}.{sys.version_info.minor}"
    return None, (
        f"上游引擎需要 Python 3.12+（当前 {sys.version_info.major}.{sys.version_info.minor}），"
        f"请设置 {UPSTREAM_PYTHON_ENV} 指向 3.12+ 解释器"
    )


def status() -> Dict[str, Any]:
    script = find_upstream()
    python, python_note = upstream_python()
    return {
        "installed": bool(script),
        "script": str(script) if script else None,
        "python": python,
        "python_note": python_note,
        "ready": bool(script and python),
    }


def build_command(
    script: Path,
    python: str,
    query: str,
    from_date: str,
    to_date: str,
    depth: str,
    platforms: Sequence[str],
) -> List[str]:
    from datetime import datetime
    days = (datetime.strptime(to_date, "%Y-%m-%d") - datetime.strptime(from_date, "%Y-%m-%d")).days or 30
    cmd = [python, str(script), query, "--emit", "json", "--json-profile", "raw",
           "--days", str(days), "--as-of", to_date]
    if platforms:
        cmd += ["--search", ",".join(platforms)]
    if depth == "quick":
        cmd.append("--quick")
    elif depth == "deep":
        cmd.append("--deep")
    return cmd


def _extract_json(stdout: str) -> Dict[str, Any]:
    text = (stdout or "").strip()
    try:
        return json.loads(text)
    except ValueError:
        start = text.find("{")
        if start >= 0:
            return json.loads(text[start:])
        raise


def map_items(payload: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """Map upstream ``items_by_source`` (raw profile) into CN global items."""
    items: List[Dict[str, Any]] = []
    errors = dict(payload.get("errors_by_source") or {})
    by_source = payload.get("items_by_source") or {}
    if not isinstance(by_source, dict):
        by_source = {}
    for platform, rows in by_source.items():
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            url = row.get("url") or ""
            title = row.get("title") or row.get("snippet") or row.get("body") or ""
            if not url or not title:
                continue
            published = row.get("published_at") or ""
            engagement = {}
            for key, value in (row.get("engagement") or {}).items():
                if not isinstance(value, (int, float)):
                    continue
                lowered = key.lower()
                if lowered in ("score", "points", "upvotes", "ups"):
                    engagement["score"] = int(value)
                elif lowered in ("likes", "like_count", "favorite_count", "favorites", "digg_count"):
                    engagement["likes"] = int(value)
                elif lowered in ("views", "view_count", "play_count", "plays", "impressions"):
                    engagement["views"] = int(value)
                elif lowered in ("comments", "num_comments", "comment_count", "replies", "reply_count"):
                    engagement["comments"] = int(value)
                elif lowered in ("reposts", "retweets", "shares", "share_count", "retweet_count"):
                    engagement["reposts"] = int(value)
            items.append({
                "platform": str(row.get("source") or platform),
                "title": str(title)[:200],
                "url": url,
                "text": str(row.get("snippet") or row.get("body") or "")[:300],
                "author": row.get("author") or "",
                "container": row.get("container") or "",
                "date": published[:10] if published else None,
                "date_confidence": row.get("date_confidence") or ("med" if published else "low"),
                "engagement": engagement,
                "why_relevant": row.get("why_relevant") or f"上游 last30days · {platform}",
                "source": f"upstream:{platform}",
            })
    return items, errors


def search_upstream(
    query: str,
    from_date: str,
    to_date: str,
    depth: str = "default",
    platforms: Optional[Sequence[str]] = None,
    timeout: int = 300,
) -> List[Dict[str, Any]]:
    script = find_upstream()
    if not script:
        raise http.HTTPError(
            "未找到上游 last30days 引擎；安装：npx skills add mvanhorn/last30days-skill -g，"
            f"或设置 {UPSTREAM_ENV} 指向其 scripts/last30days.py"
        )
    python, note = upstream_python()
    if not python:
        raise http.HTTPError(note)
    if not platforms:
        env_platforms = os.environ.get(UPSTREAM_SEARCH_ENV, "").strip()
        platforms = [p.strip() for p in env_platforms.split(",") if p.strip()] or list(DEFAULT_PLATFORMS)
    cmd = build_command(script, python, query, from_date, to_date, depth, platforms)
    http.log(f"[upstream] {' '.join(cmd[:2])} ... --search {','.join(platforms)}")
    env = dict(os.environ)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout, env=env, cwd=str(script.parent),
        )
    except subprocess.TimeoutExpired:
        raise http.HTTPError(f"上游引擎超时（{timeout}s）")
    if proc.returncode != 0:
        tail = " ".join((proc.stderr or proc.stdout or "").strip().splitlines()[-3:])
        raise http.HTTPError(f"上游引擎退出码 {proc.returncode}: {tail[:300]}")
    try:
        payload = _extract_json(proc.stdout)
    except ValueError:
        raise http.HTTPError("上游引擎未输出可解析的 JSON（请确认其版本支持 --json-profile raw）")
    items, errors = map_items(payload)
    if errors:
        summary = "；".join(f"{k}: {str(v)[:80]}" for k, v in list(errors.items())[:4])
        sys.stderr.write(f"[海外平台] 上游部分来源不可用：{summary}\n")
    if not items and errors:
        raise http.HTTPError("上游引擎没有返回结果：" + "；".join(f"{k}: {str(v)[:60]}" for k, v in errors.items()))
    from . import relevance

    for item in items:
        # Upstream already filtered for relevance; keep a floor so its ranking
        # signal is not erased by our stricter token-overlap metric.
        score = relevance.token_overlap_relevance(query, f"{item['title']} {item['text']}")
        item["relevance"] = max(0.4, score)
    items.sort(key=lambda x: x["relevance"], reverse=True)
    for i, item in enumerate(items):
        item["id"] = f"UP{i+1}"
    return items
