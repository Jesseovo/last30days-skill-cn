# last30days-cn — notes for agents and contributors

## What this repo is

`last30days-cn` is an Agent Skill that researches what people said in the last 30 days (Beijing time) on Weibo, Xiaohongshu, Bilibili, Zhihu, Douyin, WeChat public accounts, Baidu and Toutiao. It ranks results by relevance, recency and engagement, links the same event across platforms, and renders compact Markdown, a full Markdown report, JSON and an HTML report.

It also provides:

- `--hot`: a cross-platform hot-search board (Weibo, Baidu, Douyin, Toutiao, Bilibili, Zhihu, optional RSS and Hacker News).
- `login <platform>`: saves a browser session for login-gated platforms.
- Opt-in overseas sources: Hacker News, GitHub, Reddit, and a bridge to an installed `mvanhorn/last30days` for X/YouTube/TikTok/Instagram.

## Layout

- `SKILL.md`: source of truth for the skill instructions agents read.
- `scripts/`: source of truth for the runtime.
  - `last30days.py`: CLI entry (research, `--hot`, `login`, `--diagnose`, `setup`).
  - `lib/sources.py`: source registry (id, label, section, ID prefix, group, aliases). Every source starts here.
  - `lib/pipeline.py`: per-source adapters, normalizers and scorers, plus the parallel run with per-source deadlines and status.
  - `lib/http.py`: browser-grade headers (`browser_headers()`), gzip/charset decoding, cookie `Session`, `fetch()`, retry policy, 412 fast-fail.
  - `lib/websearch.py`: multi-engine public web-search fallback with URL-pattern and relevance validation.
  - `lib/crawler_bridge.py`: Playwright: login flow, cookie import, circuit breaker, concurrency limit, per-platform browser crawlers.
  - Platform adapters: `weibo.py`, `xiaohongshu.py`, `bilibili.py`, `zhihu.py`, `douyin.py`, `wechat.py`, `baidu.py`, `toutiao.py`. Overseas: `hackernews.py`, `github.py`, `reddit.py`, `upstream_bridge.py`.
  - `lib/trending.py`: `--hot`. `lib/render.py`: output. `lib/doctor.py`: `--diagnose`. `lib/env.py`: configuration.
- `skills/last30days/`: the generated, installable payload. **Never edit by hand.**
- `tests/`: regression tests (no network access).
- `.github/workflows/`: `ci.yml` (Linux/Windows/macOS, Python 3.8–3.12) and `daily-hot.yml` (opt-in GitHub Pages hot board, enabled by the repository variable `HOT_PAGES=true`).

## Ground rules

- Edit only the root `SKILL.md` and `scripts/`, then regenerate the payload:
  ```bash
  python scripts/build_payload.py
  python scripts/build_payload.py --check
  ```
- The runtime is standard-library only and must run on **Python 3.8**. That rules out `list[...]` / `X | Y` runtime annotations, `str.removeprefix`, parenthesized multi-item `with`, and `match`. `tests/test_env_cli_v4.py` enforces this. `jieba` and `playwright` stay optional.
- Platform requests go through `http.browser_headers()`. Never hand-write a User-Agent, because WAFs reject truncated ones with HTTP 412.
- Adapters return dicts that carry a `source` field naming the data path (e.g. `wbi-search`, `so.toutiao`, `site-search:ddg`). When every path fails, raise `http.HTTPError` with a human-readable reason and the fix (e.g. `login xiaohongshu`). Never fail silently with an empty list.
- Web-search fallbacks call `websearch.site_search(..., url_pattern=...)` so only real content URLs for that platform are accepted.
- Dates use Beijing time (`dates.CST`). Tests that compare against "today" must use `datetime.now(dates.CST)`.
- Secrets: cookies and keys come from `.env` into `config`, are never exported to `os.environ`, and are never logged (`http._redact_url`). Browser sessions are written 0600. The SessionStart hook parses `.env` without `eval`.
- Tests must not touch the network. Mock `lib.http` functions, `websearch._ENGINE_FUNCS`, or the platform `fetch_*` helpers.

## Adding a source

1. Add a `SourceSpec` in `lib/sources.py` (unique ID prefix, group `cn` or `global`, aliases).
2. Write the adapter module: it returns item dicts with a `source` field and raises `http.HTTPError` with a fix on hard failure.
3. Register it in `lib/pipeline.py` (`SEARCHERS`, `NORMALIZERS`, `SCORERS`) and add a timeout key to `TIMEOUT_PROFILES`.
4. Add the report list and error fields in `lib/schema.py`. Overseas sources reuse `GlobalItem`.
5. Add engagement labels in `render._ENGAGEMENT_FIELDS`, and a diagnostics entry in `lib/doctor.py` if it needs setup.
6. Add parser tests with small fixtures that copy the real response structure.

## Commands

```bash
python scripts/last30days.py "你的主题" --emit compact
python scripts/last30days.py "你的主题" --emit html-path
python scripts/last30days.py --hot
python scripts/last30days.py --diagnose            # add --probe-browser to launch the browser once
python scripts/last30days.py login xiaohongshu     # weibo | zhihu | douyin | bilibili
```

Validate on this Windows workspace with:

```bash
python -m pytest tests -q
python scripts/build_payload.py --check
python -m compileall -q scripts
```

The `python` command may resolve to the Windows Store shim on some machines; `py` works as well.

## Releasing

1. Bump `scripts/lib/version.py`, then match it in `SKILL.md`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` and `gemini-extension.json` (`tests/test_version.py` checks they agree).
2. Add a section to `release-notes.md`; that's where version history lives, not the README.
3. Regenerate the payload, run the tests, and tag `vX.Y.Z`.
