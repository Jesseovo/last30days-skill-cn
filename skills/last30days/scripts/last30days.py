#!/usr/bin/env python3
"""
last30days-cn - 研究过去 N 天内中国平台（及可选海外平台）上的真实讨论。

Author: Jesse (https://github.com/Jesseovo)

Usage:
    python3 last30days.py <topic> [options]          # 主题研究
    python3 last30days.py login <platform> [--cookie "..."]   # 保存平台登录态
    python3 last30days.py --diagnose [--probe-browser] # 数据源诊断
    python3 last30days.py setup                         # 首次配置

Options (research):
    --emit=MODE         compact|json|md|html|context|path|html-path (default: compact)
    --quick / --deep    检索深度
    --days N            回溯天数 (1-30, default: 30)
    --as-of DATE        历史回溯终点 YYYY-MM-DD
    --search SOURCES    逗号分隔：平台 id / 别名 / 分组（cn, global, all）
                        weibo,xiaohongshu(xhs),bilibili,zhihu,douyin,wechat,baidu,toutiao,
                        hackernews(hn),github,reddit,upstream(x,youtube,tiktok,instagram)
    --global            额外启用海外源 Hacker News / GitHub / Reddit
    --global-query Q    海外源使用的英文关键词（中文主题时需要）
    --no-browser        本次运行禁用 Playwright（旧电脑 / 无图形环境）
"""

import argparse
import json
import os
import signal
import sys
import threading
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR))

from lib import (  # noqa: E402
    cache,
    crawler_bridge,
    dates,
    doctor,
    env,
    pipeline,
    query,
    render,
    schema,
    setup_wizard,
    sources,
)
from lib import query_type as qt  # noqa: E402
from lib.version import DISPLAY_VERSION  # noqa: E402

TIMEOUT_PROFILES = pipeline.TIMEOUT_PROFILES

# 8 个规范中文源（不含别名），用于默认/排除集合运算
ALL_SOURCE_IDS = set(sources.CN_SOURCE_IDS)
GLOBAL_SOURCE_IDS = set(sources.GLOBAL_SOURCE_IDS)
VALID_SEARCH_SOURCES = set(sources.valid_tokens())

LOGIN_WORDS = {"login", "登录"}


def parse_search_flag(search_str: str) -> set:
    """Parse ``--search`` (ids, aliases and groups). Exits on unknown tokens."""
    try:
        ids, _upstream = sources.parse_list(search_str)
    except sources.UnknownSourceError as exc:
        print(
            f"错误: 未知搜索源 '{exc}'。可用: {', '.join(sources.valid_tokens())}",
            file=sys.stderr,
        )
        sys.exit(1)
    if not ids:
        print("错误: --search 需要至少一个搜索源。", file=sys.stderr)
        sys.exit(1)
    return ids


def _env_source_set(name: str) -> set:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return set()
    try:
        return sources.parse_list(raw)[0]
    except sources.UnknownSourceError as exc:
        print(f"警告: 环境变量 {name} 含未知源 '{exc}'，已忽略。", file=sys.stderr)
        return set()


def resolve_search_sources(cli_search, include_global: bool = False):
    """解析最终启用的搜索源。

    优先级: --search > 环境变量 LAST30DAYS_DEFAULT_SEARCH > 全部中文源；
    再并上 INCLUDE_SOURCES / --global，最后减去 EXCLUDE_SOURCES。

    返回 None 表示"使用默认集合"（全部中文源；--quick 时按查询类型分层）。
    """
    sources_set = None
    if cli_search:
        sources_set = parse_search_flag(cli_search)
    else:
        default_env = os.environ.get("LAST30DAYS_DEFAULT_SEARCH", "").strip()
        if default_env:
            sources_set = parse_search_flag(default_env)

    included = _env_source_set("INCLUDE_SOURCES")
    if include_global:
        included |= set(sources.NATIVE_GLOBAL_IDS)
    if included:
        sources_set = (sources_set if sources_set is not None else set(ALL_SOURCE_IDS)) | included

    excluded = _env_source_set("EXCLUDE_SOURCES")
    if excluded:
        base = sources_set if sources_set is not None else set(ALL_SOURCE_IDS)
        sources_set = base - excluded
        if not sources_set:
            print("错误: EXCLUDE_SOURCES 排除后没有可用搜索源。", file=sys.stderr)
            sys.exit(1)

    return sources_set


def _upstream_platforms(cli_search) -> list:
    platforms = set()
    for raw in (cli_search, os.environ.get("INCLUDE_SOURCES", "")):
        if raw:
            try:
                platforms |= sources.parse_list(raw)[1]
            except sources.UnknownSourceError:
                pass
    return sorted(platforms)


def _install_global_timeout(timeout_seconds: int):
    def _report():
        sys.stderr.write(f"\n[超时] 全局超时 ({timeout_seconds}s) 已超过，退出。可用 --timeout 调整或 --quick 加速。\n")
        sys.stderr.flush()

    if hasattr(signal, "SIGALRM"):
        def _handler(signum, frame):
            _report()
            os._exit(124)
        signal.signal(signal.SIGALRM, _handler)
        signal.alarm(timeout_seconds)
    else:
        def _watchdog():
            _report()
            os._exit(124)
        timer = threading.Timer(timeout_seconds, _watchdog)
        timer.daemon = True
        timer.start()


def _cache_sources_token(depth: str, search_sources, query_type: str, extra: str = "") -> str:
    source_part = ",".join(sorted(search_sources)) if search_sources else f"auto:{query_type}"
    return f"v4|{depth}|{source_part}|{extra}"


def _save_raw_output(args, report: schema.Report) -> None:
    if not args.save_dir:
        return
    import re as re_mod

    save_dir = Path(args.save_dir).expanduser()
    save_dir.mkdir(parents=True, exist_ok=True)
    slug = re_mod.sub(r"[^a-z0-9一-鿿]+", "-", report.topic.lower()).strip("-")[:60] or "report"
    save_path = save_dir / f"{slug}-raw.md"
    if save_path.exists():
        save_path = save_dir / f"{slug}-raw-{datetime.now().strftime('%Y-%m-%d-%H%M%S')}.md"
    content = render.render_compact(report) + "\n" + render.render_source_status(report)
    save_path.write_text(content, encoding="utf-8")
    print(f"已保存: {save_path}", file=sys.stderr)


def _emit(args, report: schema.Report) -> None:
    if args.emit == "compact":
        print(render.render_compact(report))
        print(render.render_source_status(report))
    elif args.emit == "json":
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    elif args.emit == "md":
        print(render.render_full_report(report))
    elif args.emit == "html":
        print(render.render_html_report(report))
    elif args.emit == "context":
        print(report.context_snippet_md)
    elif args.emit == "path":
        print(render.get_context_path())
    elif args.emit == "html-path":
        print(render.get_html_path())
    _save_raw_output(args, report)


def run_research(
    topic: str,
    config: dict,
    from_date: str,
    to_date: str,
    depth: str = "default",
    timeouts: dict = None,
    search_sources: set = None,
    query_type: str = "breaking_news",
    overseas_query: str = None,
    upstream_platforms=(),
) -> dict:
    """Run the selected sources (compat wrapper around lib.pipeline)."""
    ctx = pipeline.RunContext(
        topic=topic, search_topic=topic, from_date=from_date, to_date=to_date,
        depth=depth, config=config, overseas_query=overseas_query,
        upstream_platforms=tuple(upstream_platforms),
    )
    active = pipeline.select_sources(search_sources, query_type, depth)
    return pipeline.run_sources(ctx, active, timeouts or TIMEOUT_PROFILES[depth])


# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------

def _run_login(platform: str, cookie: str, timeout: int) -> int:
    try:
        platform = sources.resolve_token(platform)[0] if platform else ""
    except sources.UnknownSourceError:
        pass
    if platform not in crawler_bridge.LOGIN_SPECS:
        print(
            f"用法: last30days.py login <{'|'.join(crawler_bridge.LOGIN_SPECS)}> [--cookie \"浏览器复制的 Cookie\"]",
            file=sys.stderr,
        )
        return 1
    if cookie:
        try:
            count = crawler_bridge.import_cookie_header(platform, cookie)
        except ValueError as exc:
            print(f"导入失败: {exc}", file=sys.stderr)
            return 1
        print(f"已导入 {crawler_bridge.LOGIN_SPECS[platform]['label']} Cookie（{count} 个字段），保存在 {crawler_bridge.COOKIE_DIR}")
        return 0
    ok, message = crawler_bridge.interactive_login(platform, timeout_seconds=timeout)
    print(message, file=sys.stdout if ok else sys.stderr)
    return 0 if ok else 1


def main():
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="研究过去 N 天内中国平台（及可选海外平台）上的真实讨论",
    )
    parser.add_argument("topic", nargs="*", help="研究主题；或 login <平台> / setup")
    parser.add_argument("--emit", choices=["compact", "json", "md", "html", "context", "path", "html-path"], default="compact", help="输出模式")
    parser.add_argument("--quick", action="store_true", help="快速搜索（按查询类型选择平台）")
    parser.add_argument("--deep", action="store_true", help="深度搜索")
    parser.add_argument("--debug", action="store_true", help="启用调试日志")
    parser.add_argument("--days", type=int, default=30, choices=range(1, 31), metavar="N", help="回溯天数 (1-30)")
    parser.add_argument("--as-of", dest="as_of", type=str, default=None, metavar="YYYY-MM-DD", help="历史回溯：以指定日期为终点回溯 N 天")
    parser.add_argument("--diagnose", action="store_true", help="显示数据源诊断")
    parser.add_argument("--probe-browser", action="store_true", help="诊断时真实启动一次浏览器")
    parser.add_argument("--timeout", type=int, default=None, metavar="SECS", help="全局超时秒数")
    parser.add_argument("--search", type=str, default=None, metavar="SOURCES", help="逗号分隔的搜索源/分组（cn, global, all）")
    parser.add_argument("--global", dest="include_global", action="store_true", help="额外启用 Hacker News / GitHub / Reddit")
    parser.add_argument("--global-query", type=str, default=None, metavar="Q", help="海外源使用的英文关键词")
    parser.add_argument("--no-browser", action="store_true", help="本次运行禁用 Playwright 浏览器")
    parser.add_argument("--save-dir", type=str, default=None, metavar="DIR", help="自动保存原始输出")
    parser.add_argument("--no-cache", action="store_true", help="跳过缓存读取与写入")
    parser.add_argument("--refresh", action="store_true", help="忽略缓存并刷新结果")
    parser.add_argument("--cache-ttl", type=int, default=cache.DEFAULT_TTL_HOURS, metavar="HOURS", help="缓存有效期小时数")
    parser.add_argument("--cookie", type=str, default=None, help="login 时直接导入浏览器复制的 Cookie")
    parser.add_argument("--login-timeout", type=int, default=240, metavar="SECS", help="login 等待扫码的秒数")
    parser.add_argument("--version", action="version", version=f"last30days-cn {DISPLAY_VERSION}")

    args = parser.parse_args()
    words = list(args.topic or [])
    args.topic = " ".join(words) if words else None

    if args.debug:
        os.environ["LAST30DAYS_DEBUG"] = "1"

    config = env.get_config()  # also exports runtime switches from .env files
    if args.no_browser:
        os.environ["LAST30DAYS_DISABLE_BROWSER"] = "1"

    if args.quick and args.deep:
        print("错误: 不能同时使用 --quick 和 --deep", file=sys.stderr)
        sys.exit(1)
    depth = "quick" if args.quick else ("deep" if args.deep else "default")
    timeouts = TIMEOUT_PROFILES[depth]

    # --- login ---------------------------------------------------------------
    if words and words[0].lower() in LOGIN_WORDS:
        sys.exit(_run_login(words[1].lower() if len(words) > 1 else "", args.cookie, args.login_timeout))

    # --- diagnose --------------------------------------------------------------
    if args.diagnose:
        diag = doctor.build_report(config, probe_browser=args.probe_browser)
        if args.emit == "json":
            print(json.dumps(doctor.render_json(diag), indent=2, ensure_ascii=False))
        else:
            print(doctor.render_text(diag))
        sys.exit(0)

    # --- setup -----------------------------------------------------------------
    if args.topic and args.topic.strip().lower() == "setup":
        results = setup_wizard.run_auto_setup(config)
        results["env_written"] = setup_wizard.write_setup_config(env.CONFIG_FILE) if env.CONFIG_FILE else False
        print(setup_wizard.get_setup_status_text(results))
        sys.exit(0)

    if not args.topic:
        print("错误: 请提供研究主题。", file=sys.stderr)
        print("用法: python3 last30days.py <topic> [options]", file=sys.stderr)
        sys.exit(1)

    # --- research --------------------------------------------------------------
    try:
        from_date, to_date = dates.get_date_range(args.days, as_of=args.as_of)
    except ValueError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)

    search_sources = resolve_search_sources(args.search, include_global=args.include_global)
    upstream_platforms = _upstream_platforms(args.search)
    query_type = qt.detect_query_type(args.topic)
    search_topic = query.search_keyword(args.topic)
    overseas_query = query.overseas_query(args.topic, args.global_query)
    active = pipeline.select_sources(search_sources, query_type, depth)

    upstream_timeout = timeouts.get("upstream_future", 300)
    global_timeout = args.timeout or timeouts["global"]
    if "upstream" in active and not args.timeout:
        global_timeout = max(global_timeout, upstream_timeout + 90)
    _install_global_timeout(global_timeout)

    cache_key = cache.get_cache_key(
        args.topic, from_date, to_date,
        _cache_sources_token(depth, set(active), query_type, f"{overseas_query or ''}|{','.join(upstream_platforms)}"),
    )

    sys.stderr.write(f"正在搜索: {args.topic}\n")
    if search_topic != args.topic:
        sys.stderr.write(f"平台检索词: {search_topic}\n")
    if any(sid in GLOBAL_SOURCE_IDS for sid in active):
        sys.stderr.write(f"海外检索词: {overseas_query or '（未提供，中文主题请加 --global-query）'}\n")
    sys.stderr.write(f"查询类型: {query_type} | 日期范围: {from_date} 至 {to_date} | 平台: {', '.join(active)}\n")
    sys.stderr.flush()

    if not args.no_cache and not args.refresh:
        cached_data, age_hours = cache.load_cache_with_age(cache_key, ttl_hours=args.cache_ttl)
        if cached_data:
            report = schema.Report.from_dict(cached_data)
            report.from_cache = True
            report.cache_age_hours = age_hours
            if not report.context_snippet_md:
                report.context_snippet_md = render.render_context_snippet(report)
            render.write_outputs(report)
            age_text = f"{age_hours:.1f}" if age_hours is not None else "未知"
            sys.stderr.write(f"⚡ 使用缓存结果（约 {age_text} 小时前，--refresh 可强制刷新）\n")
            sys.stderr.flush()
            _emit(args, report)
            return

    ctx = pipeline.RunContext(
        topic=args.topic,
        search_topic=search_topic,
        from_date=from_date,
        to_date=to_date,
        depth=depth,
        config=config,
        overseas_query=overseas_query,
        upstream_platforms=tuple(upstream_platforms),
        upstream_timeout=upstream_timeout,
    )
    raw_results = pipeline.run_sources(ctx, active, timeouts)

    sys.stderr.write("正在处理结果...\n")
    sys.stderr.flush()
    processed = pipeline.process_results(raw_results, from_date, to_date, query_type)
    report = pipeline.build_report(args.topic, ctx, raw_results, processed, query_type)
    report.context_snippet_md = render.render_context_snippet(report)
    render.write_outputs(report)
    if not args.no_cache and any(report.items(sid) for sid in active):
        cache.save_cache(cache_key, report.to_dict())

    total = sum(len(report.items(sid)) for sid in active)
    sys.stderr.write(f"\n完成! 共 {total} 条结果（{render.get_html_path()}）\n")
    sys.stderr.flush()

    _emit(args, report)


if __name__ == "__main__":
    main()
