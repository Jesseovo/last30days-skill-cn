#!/usr/bin/env python3
"""
last30days-cn - 研究过去30天内中国平台上的热门话题。

Author: Jesse (https://github.com/ChiTing111)

Usage:
    python3 last30days.py <topic> [options]

Options:
    --emit=MODE         输出模式: compact|json|md|context|path (default: compact)
    --quick             快速搜索，减少数据源
    --deep              深度搜索，更多数据源
    --debug             启用调试日志
    --days N            回溯天数 (1-30, default: 30)
    --search SOURCES    指定搜索源 (逗号分隔): weibo,xiaohongshu,bilibili,zhihu,douyin,wechat,baidu,toutiao
    --diagnose          显示数据源可用性诊断
"""

import argparse
import atexit
import json
import os
import signal
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR))

_child_pids: set = set()
_child_pids_lock = threading.Lock()

TIMEOUT_PROFILES = {
    "quick":   {"global": 90,  "future": 30, "weibo_future": 30, "bilibili_future": 30, "zhihu_future": 30, "douyin_future": 60, "xiaohongshu_future": 30, "wechat_future": 30, "baidu_future": 30, "toutiao_future": 15, "http": 15},
    "default": {"global": 180, "future": 60, "weibo_future": 60, "bilibili_future": 60, "zhihu_future": 60, "douyin_future": 90, "xiaohongshu_future": 60, "wechat_future": 60, "baidu_future": 60, "toutiao_future": 30, "http": 30},
    "deep":    {"global": 300, "future": 90, "weibo_future": 90, "bilibili_future": 90, "zhihu_future": 90, "douyin_future": 120, "xiaohongshu_future": 90, "wechat_future": 90, "baidu_future": 90, "toutiao_future": 45, "http": 30},
}

VALID_SEARCH_SOURCES = {
    "weibo", "xiaohongshu", "xhs", "bilibili", "zhihu",
    "douyin", "wechat", "baidu", "toutiao",
}


def parse_search_flag(search_str: str) -> set:
    sources = set()
    for s in search_str.split(","):
        s = s.strip().lower()
        if not s:
            continue
        if s == "xhs":
            s = "xiaohongshu"
        if s not in VALID_SEARCH_SOURCES:
            print(f"错误: 未知搜索源 '{s}'。可用: {', '.join(sorted(VALID_SEARCH_SOURCES))}", file=sys.stderr)
            sys.exit(1)
        sources.add(s)
    if not sources:
        print("错误: --search 需要至少一个搜索源。", file=sys.stderr)
        sys.exit(1)
    return sources


def register_child_pid(pid: int):
    with _child_pids_lock:
        _child_pids.add(pid)

def unregister_child_pid(pid: int):
    with _child_pids_lock:
        _child_pids.discard(pid)

def _cleanup_children():
    with _child_pids_lock:
        pids = list(_child_pids)
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError, OSError):
            pass

atexit.register(_cleanup_children)


def _install_global_timeout(timeout_seconds: int):
    if hasattr(signal, 'SIGALRM'):
        def _handler(signum, frame):
            sys.stderr.write(f"\n[超时] 全局超时 ({timeout_seconds}s) 已超过。正在清理。\n")
            sys.stderr.flush()
            _cleanup_children()
            sys.exit(1)
        signal.signal(signal.SIGALRM, _handler)
        signal.alarm(timeout_seconds)
    else:
        def _watchdog():
            sys.stderr.write(f"\n[超时] 全局超时 ({timeout_seconds}s) 已超过。正在清理。\n")
            sys.stderr.flush()
            _cleanup_children()
            os._exit(1)
        timer = threading.Timer(timeout_seconds, _watchdog)
        timer.daemon = True
        timer.start()


from lib import (
    weibo,
    xiaohongshu,
    bilibili,
    zhihu,
    douyin,
    wechat,
    baidu,
    toutiao,
    dates,
    dedupe,
    env,
    normalize,
    query,
    render,
    schema,
    score,
    setup_wizard,
    query_type as qt,
)


def _search_weibo(topic, config, from_date, to_date, depth):
    try:
        token = config.get("WEIBO_ACCESS_TOKEN")
        items = weibo.search_weibo(topic, from_date, to_date, depth=depth, token=token)
        return items, None
    except Exception as e:
        return [], f"{type(e).__name__}: {e}"

def _search_xiaohongshu(topic, config, from_date, to_date, depth):
    try:
        token = config.get("SCRAPECREATORS_API_KEY")
        api_base = env.get_xiaohongshu_api_base(config)
        items = xiaohongshu.search_xiaohongshu(topic, from_date, to_date, depth=depth, token=token, api_base=api_base)
        return items, None
    except Exception as e:
        return [], f"{type(e).__name__}: {e}"

def _search_bilibili(topic, from_date, to_date, depth):
    try:
        items = bilibili.search_bilibili(topic, from_date, to_date, depth=depth)
        return items, None
    except Exception as e:
        return [], f"{type(e).__name__}: {e}"

def _search_zhihu(topic, config, from_date, to_date, depth):
    try:
        cookie = config.get("ZHIHU_COOKIE")
        items = zhihu.search_zhihu(topic, from_date, to_date, depth=depth, cookie=cookie)
        return items, None
    except Exception as e:
        return [], f"{type(e).__name__}: {e}"

def _search_douyin(topic, config, from_date, to_date, depth):
    try:
        token = config.get("TIKHUB_API_KEY") or config.get("DOUYIN_API_KEY")
        items = douyin.search_douyin(topic, from_date, to_date, depth=depth, token=token)
        return items, None
    except Exception as e:
        return [], f"{type(e).__name__}: {e}"

def _search_wechat(topic, config, from_date, to_date, depth):
    try:
        api_key = config.get("WECHAT_API_KEY")
        items = wechat.search_wechat(topic, from_date, to_date, depth=depth, api_key=api_key)
        return items, None
    except Exception as e:
        return [], f"{type(e).__name__}: {e}"

def _search_baidu(topic, config, from_date, to_date, depth):
    try:
        api_key = config.get("BAIDU_API_KEY")
        secret_key = config.get("BAIDU_SECRET_KEY")
        items = baidu.search_baidu(topic, from_date, to_date, depth=depth, api_key=api_key, secret_key=secret_key)
        return items, None
    except Exception as e:
        return [], f"{type(e).__name__}: {e}"

def _search_toutiao(topic, from_date, to_date, depth):
    try:
        items = toutiao.search_toutiao(topic, from_date, to_date, depth=depth)
        return items, None
    except Exception as e:
        return [], f"{type(e).__name__}: {e}"


def run_research(
    topic: str,
    config: dict,
    from_date: str,
    to_date: str,
    depth: str = "default",
    timeouts: dict = None,
    search_sources: set = None,
    query_type: str = "breaking_news",
) -> dict:
    if timeouts is None:
        timeouts = TIMEOUT_PROFILES[depth]
    future_timeout = timeouts["future"]

    all_sources = {"weibo", "xiaohongshu", "bilibili", "zhihu", "douyin", "wechat", "baidu", "toutiao"}
    if search_sources:
        active = search_sources & all_sources
    else:
        active = {s for s in all_sources if qt.is_source_enabled(s, query_type)}

    results = {src: {"items": [], "error": None} for src in all_sources}

    futures = {}
    max_workers = len(active)

    with ThreadPoolExecutor(max_workers=max(max_workers, 1)) as executor:
        if "weibo" in active:
            sys.stderr.write("[微博] 搜索中...\n")
            futures["weibo"] = executor.submit(_search_weibo, topic, config, from_date, to_date, depth)
        if "xiaohongshu" in active:
            sys.stderr.write("[小红书] 搜索中...\n")
            futures["xiaohongshu"] = executor.submit(_search_xiaohongshu, topic, config, from_date, to_date, depth)
        if "bilibili" in active:
            sys.stderr.write("[B站] 搜索中...\n")
            futures["bilibili"] = executor.submit(_search_bilibili, topic, from_date, to_date, depth)
        if "zhihu" in active:
            sys.stderr.write("[知乎] 搜索中...\n")
            futures["zhihu"] = executor.submit(_search_zhihu, topic, config, from_date, to_date, depth)
        if "douyin" in active:
            sys.stderr.write("[抖音] 搜索中...\n")
            futures["douyin"] = executor.submit(_search_douyin, topic, config, from_date, to_date, depth)
        if "wechat" in active:
            sys.stderr.write("[微信] 搜索中...\n")
            futures["wechat"] = executor.submit(_search_wechat, topic, config, from_date, to_date, depth)
        if "baidu" in active:
            sys.stderr.write("[百度] 搜索中...\n")
            futures["baidu"] = executor.submit(_search_baidu, topic, config, from_date, to_date, depth)
        if "toutiao" in active:
            sys.stderr.write("[头条] 搜索中...\n")
            futures["toutiao"] = executor.submit(_search_toutiao, topic, from_date, to_date, depth)

        for source, future in futures.items():
            timeout = timeouts.get(f"{source}_future", future_timeout)
            try:
                items, error = future.result(timeout=timeout)
                results[source]["items"] = items
                results[source]["error"] = error
                if error:
                    sys.stderr.write(f"[{source}] 错误: {error}\n")
                else:
                    sys.stderr.write(f"[{source}] {len(items)} 条结果\n")
            except TimeoutError:
                results[source]["error"] = f"{source} 搜索超时 ({timeout}s)"
                sys.stderr.write(f"[{source}] 超时 ({timeout}s)\n")
            except Exception as e:
                results[source]["error"] = f"{type(e).__name__}: {e}"
                sys.stderr.write(f"[{source}] 错误: {e}\n")

    sys.stderr.flush()
    return results


def main():
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="研究过去N天内中国平台上的热门话题")
    parser.add_argument("topic", nargs="*", help="研究主题")
    parser.add_argument("--emit", choices=["compact", "json", "md", "context", "path"], default="compact", help="输出模式")
    parser.add_argument("--quick", action="store_true", help="快速搜索")
    parser.add_argument("--deep", action="store_true", help="深度搜索")
    parser.add_argument("--debug", action="store_true", help="启用调试日志")
    parser.add_argument("--days", type=int, default=30, choices=range(1, 31), metavar="N", help="回溯天数 (1-30)")
    parser.add_argument("--diagnose", action="store_true", help="显示数据源诊断")
    parser.add_argument("--timeout", type=int, default=None, metavar="SECS", help="全局超时秒数")
    parser.add_argument("--search", type=str, default=None, metavar="SOURCES", help="逗号分隔的搜索源列表")
    parser.add_argument("--save-dir", type=str, default=None, metavar="DIR", help="自动保存原始输出")

    args = parser.parse_args()
    args.topic = " ".join(args.topic) if args.topic else None

    if args.debug:
        os.environ["LAST30DAYS_DEBUG"] = "1"

    if args.quick and args.deep:
        print("错误: 不能同时使用 --quick 和 --deep", file=sys.stderr)
        sys.exit(1)
    elif args.quick:
        depth = "quick"
    elif args.deep:
        depth = "deep"
    else:
        depth = "default"

    timeouts = TIMEOUT_PROFILES[depth]
    global_timeout = args.timeout or timeouts["global"]
    _install_global_timeout(global_timeout)

    config = env.get_config()

    if args.diagnose:
        diag = {
            "weibo": env.is_weibo_available(config),
            "xiaohongshu": env.is_xiaohongshu_available(config),
            "bilibili": True,
            "zhihu": True,
            "douyin": env.is_douyin_available(config),
            "wechat": env.is_wechat_available(config),
            "baidu_api": env.is_baidu_api_available(config),
            "toutiao": True,
            "xiaohongshu_api_base": env.get_xiaohongshu_api_base(config),
        }
        print(json.dumps(diag, indent=2, ensure_ascii=False))
        sys.exit(0)

    if args.topic and args.topic.strip().lower() == "setup":
        results = setup_wizard.run_auto_setup(config)
        env_path = env.CONFIG_FILE
        if env_path:
            written = setup_wizard.write_setup_config(env_path)
            results["env_written"] = written
        else:
            results["env_written"] = False
        print(setup_wizard.get_setup_status_text(results))
        sys.exit(0)

    if not args.topic:
        print("错误: 请提供研究主题。", file=sys.stderr)
        print("用法: python3 last30days.py <topic> [options]", file=sys.stderr)
        sys.exit(1)

    from_date, to_date = dates.get_date_range(args.days)

    search_sources = None
    if args.search:
        search_sources = parse_search_flag(args.search)

    query_type = qt.detect_query_type(args.topic)
    search_topic = query.extract_core_subject(args.topic)

    sys.stderr.write(f"正在搜索: {args.topic}\n")
    if search_topic != args.topic:
        sys.stderr.write(f"提纯关键词: {search_topic}\n")
    sys.stderr.write(f"查询类型: {query_type} | 日期范围: {from_date} 至 {to_date}\n")
    sys.stderr.flush()

    raw_results = run_research(
        search_topic, config, from_date, to_date, depth,
        timeouts=timeouts, search_sources=search_sources,
        query_type=query_type,
    )

    sys.stderr.write("正在处理结果...\n")
    sys.stderr.flush()

    norm_weibo = normalize.normalize_weibo_items(raw_results["weibo"]["items"], from_date, to_date)
    norm_xhs = normalize.normalize_xiaohongshu_items(raw_results["xiaohongshu"]["items"], from_date, to_date)
    norm_bili = normalize.normalize_bilibili_items(raw_results["bilibili"]["items"], from_date, to_date)
    norm_zhihu = normalize.normalize_zhihu_items(raw_results["zhihu"]["items"], from_date, to_date)
    norm_douyin = normalize.normalize_douyin_items(raw_results["douyin"]["items"], from_date, to_date)
    norm_wechat = normalize.normalize_wechat_items(raw_results["wechat"]["items"], from_date, to_date)
    norm_baidu = normalize.normalize_baidu_items(raw_results["baidu"]["items"], from_date, to_date)
    norm_toutiao = normalize.normalize_toutiao_items(raw_results["toutiao"]["items"], from_date, to_date)

    filt_weibo = normalize.filter_by_date_range(norm_weibo, from_date, to_date)
    filt_xhs = normalize.filter_by_date_range(norm_xhs, from_date, to_date)
    filt_bili = normalize.filter_by_date_range(norm_bili, from_date, to_date)
    filt_zhihu = normalize.filter_by_date_range(norm_zhihu, from_date, to_date)
    filt_douyin = normalize.filter_by_date_range(norm_douyin, from_date, to_date)
    filt_wechat = normalize.filter_by_date_range(norm_wechat, from_date, to_date)
    filt_baidu = normalize.filter_by_date_range(norm_baidu, from_date, to_date)
    filt_toutiao = normalize.filter_by_date_range(norm_toutiao, from_date, to_date)

    scored_weibo = score.score_weibo_items(filt_weibo)
    scored_xhs = score.score_xiaohongshu_items(filt_xhs)
    scored_bili = score.score_bilibili_items(filt_bili)
    scored_zhihu = score.score_zhihu_items(filt_zhihu)
    scored_douyin = score.score_douyin_items(filt_douyin)
    scored_wechat = score.score_wechat_items(filt_wechat, query_type=query_type)
    scored_baidu = score.score_baidu_items(filt_baidu, query_type=query_type)
    scored_toutiao = score.score_toutiao_items(filt_toutiao)

    sorted_weibo = score.sort_items(scored_weibo, query_type=query_type)
    sorted_xhs = score.sort_items(scored_xhs, query_type=query_type)
    sorted_bili = score.sort_items(scored_bili, query_type=query_type)
    sorted_zhihu = score.sort_items(scored_zhihu, query_type=query_type)
    sorted_douyin = score.sort_items(scored_douyin, query_type=query_type)
    sorted_wechat = score.sort_items(scored_wechat, query_type=query_type)
    sorted_baidu = score.sort_items(scored_baidu, query_type=query_type)
    sorted_toutiao = score.sort_items(scored_toutiao, query_type=query_type)

    deduped_weibo = dedupe.dedupe_weibo(sorted_weibo)
    deduped_xhs = dedupe.dedupe_xiaohongshu(sorted_xhs)
    deduped_bili = dedupe.dedupe_bilibili(sorted_bili)
    deduped_zhihu = dedupe.dedupe_zhihu(sorted_zhihu)
    deduped_douyin = dedupe.dedupe_douyin(sorted_douyin)
    deduped_wechat = dedupe.dedupe_wechat(sorted_wechat)
    deduped_baidu = dedupe.dedupe_baidu(sorted_baidu)
    deduped_toutiao = dedupe.dedupe_toutiao(sorted_toutiao)

    deduped_weibo = score.relevance_filter(deduped_weibo, "WEIBO")
    deduped_xhs = score.relevance_filter(deduped_xhs, "XIAOHONGSHU")
    deduped_bili = score.relevance_filter(deduped_bili, "BILIBILI")
    deduped_zhihu = score.relevance_filter(deduped_zhihu, "ZHIHU")
    deduped_douyin = score.relevance_filter(deduped_douyin, "DOUYIN")
    deduped_wechat = score.relevance_filter(deduped_wechat, "WECHAT")
    deduped_baidu = score.relevance_filter(deduped_baidu, "BAIDU")
    deduped_toutiao = score.relevance_filter(deduped_toutiao, "TOUTIAO")

    dedupe.cross_source_link(
        deduped_weibo, deduped_xhs, deduped_bili, deduped_zhihu,
        deduped_douyin, deduped_wechat, deduped_baidu, deduped_toutiao,
    )

    report = schema.create_report(args.topic, from_date, to_date, "all")
    report.weibo = deduped_weibo
    report.xiaohongshu = deduped_xhs
    report.bilibili = deduped_bili
    report.zhihu = deduped_zhihu
    report.douyin = deduped_douyin
    report.wechat = deduped_wechat
    report.baidu = deduped_baidu
    report.toutiao = deduped_toutiao
    report.weibo_error = raw_results["weibo"]["error"]
    report.xiaohongshu_error = raw_results["xiaohongshu"]["error"]
    report.bilibili_error = raw_results["bilibili"]["error"]
    report.zhihu_error = raw_results["zhihu"]["error"]
    report.douyin_error = raw_results["douyin"]["error"]
    report.wechat_error = raw_results["wechat"]["error"]
    report.baidu_error = raw_results["baidu"]["error"]
    report.toutiao_error = raw_results["toutiao"]["error"]

    report.context_snippet_md = render.render_context_snippet(report)
    render.write_outputs(report)

    total = sum(len(getattr(report, src, [])) for src in ["weibo", "xiaohongshu", "bilibili", "zhihu", "douyin", "wechat", "baidu", "toutiao"])
    sys.stderr.write(f"\n完成! 共 {total} 条结果\n")
    sys.stderr.flush()

    if args.emit == "compact":
        print(render.render_compact(report))
        print(render.render_source_status(report))
    elif args.emit == "json":
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    elif args.emit == "md":
        print(render.render_full_report(report))
    elif args.emit == "context":
        print(report.context_snippet_md)
    elif args.emit == "path":
        print(render.get_context_path())

    if args.save_dir:
        import re as re_mod
        save_dir = Path(args.save_dir).expanduser()
        save_dir.mkdir(parents=True, exist_ok=True)
        slug = re_mod.sub(r'[^a-z0-9\u4e00-\u9fff]+', '-', args.topic.lower()).strip('-')[:60]
        save_path = save_dir / f"{slug}-raw.md"
        if save_path.exists():
            save_path = save_dir / f"{slug}-raw-{datetime.now().strftime('%Y-%m-%d')}.md"
        content = render.render_compact(report)
        content += "\n" + render.render_source_status(report)
        save_path.write_text(content, encoding="utf-8")
        print(f"已保存: {save_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
