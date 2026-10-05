# last30days-cn

Agent-facing notes for local development.

## Purpose

`last30days-cn` researches recent Chinese-platform discussion across Weibo, Xiaohongshu, Bilibili, Zhihu, Douyin, WeChat public accounts, Baidu and Toutiao (default window: the last 30 days, Beijing time). It also has a cross-platform hot board (`--hot`) and opt-in overseas sources (Hacker News, GitHub, Reddit, and a bridge to upstream last30days).

## Structure

- `SKILL.md`: root development copy and source of truth for the skill instructions.
- `scripts/`: root development copy and source of truth for the runtime.
  - `lib/sources.py`: source registry (labels, ID prefixes, groups, aliases). Add new sources here first.
  - `lib/pipeline.py`: adapters, normalizers and scorers per source; parallel run with per-source deadlines.
  - `lib/http.py` / `lib/websearch.py`: shared request layer and the validated multi-engine fallback.
  - `lib/crawler_bridge.py`: Playwright (login, circuit breaker, concurrency limit).
  - `lib/trending.py`: `--hot` board. `lib/render.py`: Markdown/JSON/HTML. `lib/doctor.py`: `--diagnose`.
- `skills/last30days/`: generated installable Agent Skill payload. Never edit it by hand.
- `tests/`: regression tests. They must not touch the network; mock `lib.http`, `websearch._ENGINE_FUNCS`, etc.

Only edit the root `SKILL.md` and `scripts/` tree. Regenerate the installable
payload before committing:

```bash
python scripts/build_payload.py
python scripts/build_payload.py --check
```

## Conventions

- Runtime is stdlib-only and must stay Python 3.8 compatible: no `list[...]`/`X | Y` runtime annotations, `str.removeprefix`, parenthesized `with`, or `match`. `tests/test_env_cli_v4.py` guards this.
- Every adapter returns dicts with a `source` field naming its data path, and raises `http.HTTPError` with a human-readable reason and fix when every path fails. Never return a silent empty list for a hard failure.
- Platform requests use `http.browser_headers()`. Never hand-write a User-Agent (issue #17).
- Web-search fallbacks must pass a platform `url_pattern` to `websearch.site_search`.
- Dates are Beijing time (`dates.CST`). Tests that compare with "today" must use `datetime.now(dates.CST)`.

## Commands

```bash
python scripts/last30days.py "你的主题" --emit compact
python scripts/last30days.py "你的主题" --emit html-path
python scripts/last30days.py --hot
python scripts/last30days.py --diagnose
python scripts/last30days.py login xiaohongshu
```

When validating on this Windows workspace, prefer:

```bash
python -m pytest tests -q
```

The `python` command may resolve to the Windows Store shim on some machines.

## Release Notes

v4.0.0 rebuilt every platform adapter against live 2026 endpoints and added the source registry, pipeline, login flow, `--hot` board, overseas sources, Python 3.8 support, and the opt-in daily-hot Pages workflow. See `release-notes.md`.
