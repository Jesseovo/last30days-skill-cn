"""Research pipeline: parallel retrieval → normalize → score → dedupe → cluster.

Author: Jesse (https://github.com/Jesseovo)

v4 replaces the eight hand-written blocks in ``last30days.py`` with a loop over
the source registry, and runs sources on daemon threads with real per-source
deadlines (v3 used a ``ThreadPoolExecutor`` context manager, which still
waited for a hung source after its future timed out).
"""

import sys
import threading
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Set

from . import (
    baidu,
    bilibili,
    cluster,
    dedupe,
    douyin,
    github,
    hackernews,
    http,
    normalize,
    reddit,
    schema,
    score,
    sources,
    toutiao,
    upstream_bridge,
    wechat,
    weibo,
    xiaohongshu,
    zhihu,
)
from . import env as env_mod
from . import query_type as qt

TIMEOUT_PROFILES: Dict[str, Dict[str, int]] = {
    "quick": {
        "global": 120, "future": 30, "weibo_future": 30, "bilibili_future": 30, "zhihu_future": 30,
        "douyin_future": 45, "xiaohongshu_future": 45, "wechat_future": 25, "baidu_future": 25,
        "toutiao_future": 30, "hackernews_future": 20, "github_future": 25, "reddit_future": 20,
        "upstream_future": 240, "http": 15,
    },
    "default": {
        "global": 240, "future": 60, "weibo_future": 75, "bilibili_future": 60, "zhihu_future": 75,
        "douyin_future": 90, "xiaohongshu_future": 90, "wechat_future": 45, "baidu_future": 45,
        "toutiao_future": 45, "hackernews_future": 25, "github_future": 30, "reddit_future": 25,
        "upstream_future": 360, "http": 30,
    },
    "deep": {
        "global": 420, "future": 90, "weibo_future": 120, "bilibili_future": 90, "zhihu_future": 120,
        "douyin_future": 150, "xiaohongshu_future": 150, "wechat_future": 75, "baidu_future": 75,
        "toutiao_future": 75, "hackernews_future": 40, "github_future": 45, "reddit_future": 40,
        "upstream_future": 600, "http": 30,
    },
}


@dataclass
class RunContext:
    topic: str
    search_topic: str
    from_date: str
    to_date: str
    depth: str = "default"
    config: Dict[str, Any] = field(default_factory=dict)
    overseas_query: Optional[str] = None
    upstream_platforms: Sequence[str] = ()
    upstream_timeout: int = 300


# --- source adapters ---------------------------------------------------------

def _search_weibo(ctx: RunContext) -> List[Dict[str, Any]]:
    return weibo.search_weibo(
        ctx.search_topic, ctx.from_date, ctx.to_date, depth=ctx.depth,
        token=ctx.config.get("WEIBO_ACCESS_TOKEN"), cookie=ctx.config.get("WEIBO_COOKIE"),
    )


def _search_xiaohongshu(ctx: RunContext) -> List[Dict[str, Any]]:
    return xiaohongshu.search_xiaohongshu(
        ctx.search_topic, ctx.from_date, ctx.to_date, depth=ctx.depth,
        token=ctx.config.get("SCRAPECREATORS_API_KEY"),
        api_base=env_mod.discover_xiaohongshu_mcp(ctx.config),
    )


def _search_bilibili(ctx: RunContext) -> List[Dict[str, Any]]:
    return bilibili.search_bilibili(
        ctx.search_topic, ctx.from_date, ctx.to_date, depth=ctx.depth,
        cookie=ctx.config.get("BILIBILI_COOKIE"),
    )


def _search_zhihu(ctx: RunContext) -> List[Dict[str, Any]]:
    return zhihu.search_zhihu(
        ctx.search_topic, ctx.from_date, ctx.to_date, depth=ctx.depth,
        cookie=ctx.config.get("ZHIHU_COOKIE"),
    )


def _search_douyin(ctx: RunContext) -> List[Dict[str, Any]]:
    return douyin.search_douyin(
        ctx.search_topic, ctx.from_date, ctx.to_date, depth=ctx.depth,
        token=ctx.config.get("TIKHUB_API_KEY") or ctx.config.get("DOUYIN_API_KEY"),
    )


def _search_wechat(ctx: RunContext) -> List[Dict[str, Any]]:
    return wechat.search_wechat(
        ctx.search_topic, ctx.from_date, ctx.to_date, depth=ctx.depth,
        api_key=ctx.config.get("WECHAT_API_KEY"),
    )


def _search_baidu(ctx: RunContext) -> List[Dict[str, Any]]:
    return baidu.search_baidu(
        ctx.search_topic, ctx.from_date, ctx.to_date, depth=ctx.depth,
        api_key=ctx.config.get("BAIDU_API_KEY"), secret_key=ctx.config.get("BAIDU_SECRET_KEY"),
    )


def _search_toutiao(ctx: RunContext) -> List[Dict[str, Any]]:
    return toutiao.search_toutiao(ctx.search_topic, ctx.from_date, ctx.to_date, depth=ctx.depth)


def _require_overseas_query(ctx: RunContext, label: str) -> str:
    if not ctx.overseas_query:
        raise http.HTTPError(
            f"{label} 需要英文关键词：主题为中文时请加 --global-query \"english keywords\""
        )
    return ctx.overseas_query


def _search_hackernews(ctx: RunContext) -> List[Dict[str, Any]]:
    return hackernews.search_hackernews(
        _require_overseas_query(ctx, "Hacker News"), ctx.from_date, ctx.to_date, depth=ctx.depth
    )


def _search_github(ctx: RunContext) -> List[Dict[str, Any]]:
    return github.search_github(
        _require_overseas_query(ctx, "GitHub"), ctx.from_date, ctx.to_date, depth=ctx.depth,
        token=ctx.config.get("GITHUB_TOKEN"),
    )


def _search_reddit(ctx: RunContext) -> List[Dict[str, Any]]:
    return reddit.search_reddit(_require_overseas_query(ctx, "Reddit"), ctx.from_date, ctx.to_date, depth=ctx.depth)


def _search_upstream(ctx: RunContext) -> List[Dict[str, Any]]:
    return upstream_bridge.search_upstream(
        _require_overseas_query(ctx, "海外平台"), ctx.from_date, ctx.to_date, depth=ctx.depth,
        platforms=list(ctx.upstream_platforms) or None, timeout=ctx.upstream_timeout,
    )


SEARCHERS: Dict[str, Callable[[RunContext], List[Dict[str, Any]]]] = {
    "weibo": _search_weibo,
    "xiaohongshu": _search_xiaohongshu,
    "bilibili": _search_bilibili,
    "zhihu": _search_zhihu,
    "douyin": _search_douyin,
    "wechat": _search_wechat,
    "baidu": _search_baidu,
    "toutiao": _search_toutiao,
    "hackernews": _search_hackernews,
    "github": _search_github,
    "reddit": _search_reddit,
    "upstream": _search_upstream,
}

NORMALIZERS: Dict[str, Callable[..., List[Any]]] = {
    "weibo": normalize.normalize_weibo_items,
    "xiaohongshu": normalize.normalize_xiaohongshu_items,
    "bilibili": normalize.normalize_bilibili_items,
    "zhihu": normalize.normalize_zhihu_items,
    "douyin": normalize.normalize_douyin_items,
    "wechat": normalize.normalize_wechat_items,
    "baidu": normalize.normalize_baidu_items,
    "toutiao": normalize.normalize_toutiao_items,
    "hackernews": lambda items, f, t: normalize.normalize_global_items(items, f, t, "hackernews"),
    "github": lambda items, f, t: normalize.normalize_global_items(items, f, t, "github"),
    "reddit": lambda items, f, t: normalize.normalize_global_items(items, f, t, "reddit"),
    "upstream": lambda items, f, t: normalize.normalize_global_items(items, f, t, "upstream"),
}

SCORERS: Dict[str, Callable[[List[Any], Optional[str]], List[Any]]] = {
    "weibo": lambda items, _qt: score.score_weibo_items(items),
    "xiaohongshu": lambda items, _qt: score.score_xiaohongshu_items(items),
    "bilibili": lambda items, _qt: score.score_bilibili_items(items),
    "zhihu": lambda items, _qt: score.score_zhihu_items(items),
    "douyin": lambda items, _qt: score.score_douyin_items(items),
    "wechat": lambda items, query_type: score.score_wechat_items(items, query_type=query_type),
    "baidu": lambda items, query_type: score.score_baidu_items(items, query_type=query_type),
    "toutiao": lambda items, _qt: score.score_toutiao_items(items),
    "hackernews": lambda items, _qt: score.score_global_items(items),
    "github": lambda items, _qt: score.score_global_items(items),
    "reddit": lambda items, _qt: score.score_global_items(items),
    "upstream": lambda items, _qt: score.score_global_items(items),
}


def select_sources(
    requested: Optional[Set[str]],
    query_type: str,
    depth: str,
) -> List[str]:
    """Final ordered source list.

    v4: with no explicit request every Chinese platform runs (as documented
    since v1; v3 silently dropped platforms by query type). ``--quick`` keeps
    the query-type tiering to save time.
    """
    if requested:
        return sources.ordered(requested)
    if depth == "quick":
        return sources.ordered(s for s in sources.CN_SOURCE_IDS if qt.is_source_enabled(s, query_type))
    return list(sources.CN_SOURCE_IDS)


def _friendly_error(exc: BaseException) -> str:
    if isinstance(exc, http.HTTPError):
        return str(exc)
    return f"{type(exc).__name__}: {exc}"


def run_sources(
    ctx: RunContext,
    active: Sequence[str],
    timeouts: Optional[Dict[str, int]] = None,
    log: bool = True,
) -> Dict[str, Dict[str, Any]]:
    """Run the selected sources in parallel with per-source deadlines."""
    timeouts = timeouts or TIMEOUT_PROFILES.get(ctx.depth, TIMEOUT_PROFILES["default"])
    boxes: Dict[str, Dict[str, Any]] = {}
    threads: Dict[str, threading.Thread] = {}
    started = time.monotonic()

    for sid in active:
        box: Dict[str, Any] = {}
        boxes[sid] = box
        if log:
            sys.stderr.write(f"[{sources.label(sid)}] 搜索中...\n")

        def worker(sid=sid, box=box):
            t0 = time.monotonic()
            try:
                box["items"] = SEARCHERS[sid](ctx) or []
                box["error"] = None
            except Exception as exc:  # each source fails independently
                box["items"] = []
                box["error"] = _friendly_error(exc)
            box["elapsed"] = round(time.monotonic() - t0, 1)
            if log:
                if box["error"]:
                    sys.stderr.write(f"[{sources.label(sid)}] 失败: {box['error']}\n")
                else:
                    sys.stderr.write(f"[{sources.label(sid)}] {len(box['items'])} 条原始结果（{box['elapsed']}s）\n")

        thread = threading.Thread(target=worker, name=f"last30days-{sid}", daemon=True)
        thread.start()
        threads[sid] = thread

    results: Dict[str, Dict[str, Any]] = {}
    for sid, thread in threads.items():
        limit = timeouts.get(f"{sid}_future", timeouts.get("future", 60))
        if sid == "upstream":
            limit = max(limit, ctx.upstream_timeout + 15)
        remaining = limit - (time.monotonic() - started)
        thread.join(max(0.0, remaining))
        box = boxes[sid]
        if thread.is_alive():
            results[sid] = {
                "items": [],
                "error": f"{sources.label(sid)} 搜索超时（{limit}s），已跳过",
                "state": "timeout",
                "elapsed": float(limit),
            }
            if log:
                sys.stderr.write(f"[{sources.label(sid)}] 超时 ({limit}s)，已跳过\n")
            continue
        items = box.get("items") or []
        error = box.get("error")
        results[sid] = {
            "items": items,
            "error": error,
            "state": "error" if error and not items else ("ok" if items else "empty"),
            "elapsed": box.get("elapsed"),
            "via": dict(Counter(str(item.get("source") or "api") for item in items if isinstance(item, dict))),
        }
    if log:
        sys.stderr.flush()
    return results


def process_results(
    raw_results: Dict[str, Dict[str, Any]],
    from_date: str,
    to_date: str,
    query_type: str,
) -> Dict[str, List[Any]]:
    """Normalize → date filter → score → sort → dedupe → relevance gate → author cap."""
    processed: Dict[str, List[Any]] = {}
    for sid, result in raw_results.items():
        normalized = NORMALIZERS[sid](result.get("items") or [], from_date, to_date)
        windowed = normalize.filter_by_date_range(normalized, from_date, to_date)
        scored = SCORERS[sid](windowed, query_type)
        ordered = score.sort_items(scored, query_type=query_type)
        unique = dedupe.dedupe_items(ordered)
        relevant = score.relevance_filter(unique, sources.get(sid).code)
        processed[sid] = score.apply_per_author_cap(relevant)
    return processed


def build_report(
    topic: str,
    ctx: RunContext,
    raw_results: Dict[str, Dict[str, Any]],
    processed: Dict[str, List[Any]],
    query_type: str,
) -> schema.Report:
    lists = [processed.get(sid, []) for sid in sources.SOURCES if sid in processed]
    dedupe.cross_source_link(*lists, query=ctx.search_topic)
    clusters = cluster.build_clusters(*lists, query=ctx.search_topic)

    report = schema.create_report(topic, ctx.from_date, ctx.to_date, "all")
    report.search_topic = ctx.search_topic
    report.query_type = query_type
    report.depth = ctx.depth
    report.clusters = clusters
    for sid, items in processed.items():
        setattr(report, sid, items)
        result = raw_results.get(sid, {})
        setattr(report, f"{sid}_error", result.get("error"))
        report.source_status[sid] = {
            "state": result.get("state") if items or result.get("state") != "ok" else "empty",
            "count": len(items),
            "raw_count": len(result.get("items") or []),
            "elapsed": result.get("elapsed"),
            "via": result.get("via") or {},
        }
        if result.get("error"):
            report.source_status[sid]["error"] = result["error"]
    return report
