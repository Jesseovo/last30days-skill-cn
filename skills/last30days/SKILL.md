---
name: last30days-cn
version: "4.0.0-cn"
description: "Research what Chinese internet users actually said in the last 30 days across Weibo, Xiaohongshu (RED), Bilibili, Zhihu, Douyin, WeChat public accounts, Baidu and Toutiao: engagement-weighted ranking, cross-platform clustering, cited Markdown/JSON/HTML reports. Also shows today's cross-platform hot-search board (全网热榜, --hot) and can add Hacker News / GitHub / Reddit or an installed upstream last30days for X/YouTube/TikTok."
argument-hint: 'last30 AI 编程助手 | last30 今天全网热点 | last30 具身智能 --deep | last30 Claude Code 评测 --global'
allowed-tools: Bash, Read, Write, WebSearch
author: Jesse
license: MIT
user-invocable: true
metadata:
  openclaw:
    emoji: "📰"
    requires:
      optionalEnv:
        - WEIBO_COOKIE
        - ZHIHU_COOKIE
        - BILIBILI_COOKIE
        - TIKHUB_API_KEY
        - WECHAT_API_KEY
        - BAIDU_API_KEY
        - WEIBO_ACCESS_TOKEN
        - XIAOHONGSHU_API_BASE
        - GITHUB_TOKEN
      bins:
        - python3
    files:
      - "scripts/*"
    tags:
      - research
      - deep-research
      - chinese-platforms
      - trending
      - hot-search
      - weibo
      - xiaohongshu
      - bilibili
      - zhihu
      - douyin
      - wechat
      - baidu
      - toutiao
      - html-report
---

# last30days-cn

You are a Chinese-internet research assistant. Use this skill when the user wants recent Chinese-platform discussion, public sentiment, product reputation, trend research, "最近 30 天" coverage, or **what is trending right now** (热搜 / 热榜 / 今天有什么热点).

## Core rule

Ground every claim in the returned evidence. Never invent sources, links, engagement numbers, dates, quotes or platform sentiment. When coverage is thin or a platform failed, say so plainly.

## 1. Pick the mode

| The user asks… | Run |
|---|---|
| About a topic / product / person / event | Topic research (section 2) |
| "今天/现在有什么热点", "热搜", "全网热榜", "trending" | Hot board: `--hot` (section 3) |
| Hot topics about one theme ("今天 AI 圈有什么热点") | `--hot "<关键词>"` |
| Overseas opinion too (Reddit / HN / GitHub / X / YouTube) | Add `--global --global-query "<English keywords>"` (section 4) |
| Something is broken / which platforms work | `--diagnose` (section 6) |

`{{SKILL_DIR}}` is this skill's directory. Use `python3` (or `python` on Windows).

## 2. Topic research

```bash
python {{SKILL_DIR}}/scripts/last30days.py "{{USER_TOPIC}}" --emit compact
```

Variants:

```bash
python {{SKILL_DIR}}/scripts/last30days.py "{{USER_TOPIC}}" --quick --emit compact      # faster, query-type tiered platforms
python {{SKILL_DIR}}/scripts/last30days.py "{{USER_TOPIC}}" --deep --emit compact       # more pages per platform
python {{SKILL_DIR}}/scripts/last30days.py "{{USER_TOPIC}}" --search bilibili,zhihu,xhs --emit compact
python {{SKILL_DIR}}/scripts/last30days.py "{{USER_TOPIC}}" --days 7 --emit compact
python {{SKILL_DIR}}/scripts/last30days.py "{{USER_TOPIC}}" --as-of 2026-05-01 --emit compact
python {{SKILL_DIR}}/scripts/last30days.py "{{USER_TOPIC}}" --emit html-path           # offline HTML report path
python {{SKILL_DIR}}/scripts/last30days.py "{{USER_TOPIC}}" --refresh --emit compact    # ignore the 24h cache
python {{SKILL_DIR}}/scripts/last30days.py "{{USER_TOPIC}}" --no-cache --emit compact   # no cache read/write
```

- With no `--search`, all eight Chinese platforms run. `--search` accepts ids, aliases (`xhs`, `bili`, `hn`, `gh`) and groups (`cn`, `global`, `all`).
- 查询类型 (query type) is detected automatically (breaking_news / how_to / product / opinion / comparison / prediction / concept). It changes ranking tie-breaks, and in `--quick` mode which platforms run.
- Pass the user's own wording as the topic. The engine strips question prefixes ("大家怎么看…") but keeps casing and spacing for platform search.
- `LAST30DAYS_DEFAULT_SEARCH`, `INCLUDE_SOURCES` and `EXCLUDE_SOURCES` (env or `~/.config/last30days-cn/.env`) change the default platform set.

## 3. Hot board (全网热榜)

```bash
python {{SKILL_DIR}}/scripts/last30days.py --hot --emit compact
python {{SKILL_DIR}}/scripts/last30days.py --hot "AI" --emit compact                    # only hot items about a theme
python {{SKILL_DIR}}/scripts/last30days.py --hot --hot-sources boards,news,global --emit compact
python {{SKILL_DIR}}/scripts/last30days.py --hot --emit html-path                       # dashboard page
```

It needs no topic and fetches 微博热搜, 百度热搜, 抖音热榜, 头条热榜, B站热搜 and 知乎热榜 in parallel. `news` adds IT之家 / 虎嗅 / 少数派 / 爱范儿 / Solidot, and `global` adds the Hacker News front page. "跨平台热点" lists events that are on several boards at once.

When you present it: lead with 跨平台热点, then 2–4 notable items per platform, and say that hot lists are real-time rankings, not 30-day totals. Offer a deep-dive with `python {{SKILL_DIR}}/scripts/last30days.py "<话题>"`.

## 4. Overseas sources (opt-in)

```bash
python {{SKILL_DIR}}/scripts/last30days.py "{{USER_TOPIC}}" --global --global-query "<English keywords>" --emit compact
python {{SKILL_DIR}}/scripts/last30days.py "{{USER_TOPIC}}" --search hackernews,github,reddit --global-query "<English keywords>"
python {{SKILL_DIR}}/scripts/last30days.py "{{USER_TOPIC}}" --search x,youtube --global-query "<English keywords>"   # needs upstream last30days installed
```

- Hacker News, GitHub and Reddit need no keys. Reddit often returns 403 from cloud or proxy IPs.
- These engines don't match Chinese text. **For a Chinese topic, translate it into concise English yourself** and pass it as `--global-query`. Otherwise the overseas sources report that a query is needed.
- `x`, `youtube`, `tiktok`, `instagram` and `upstream` go through the bridge to an installed `mvanhorn/last30days` skill, which needs its own keys and Python 3.12+. If it isn't installed, tell the user: `npx skills add mvanhorn/last30days-skill -g`.

## 5. 输出契约 (output contract)

- Keep the first engine badge line exactly as printed, e.g. `🌐 last30days-cn v4.0.0-cn · 数据截至 …`. If it ends with `· 缓存`, say the evidence came from cache.
- Don't add a title before the badge and don't add a trailing `Sources:` block. Cite inline: platform name plus the URL from the evidence.
- The `**来源:**` footer shows each platform's status:
  - `✅` with a path label (`wbi-search`, `so.toutiao`, `site-search:ddg`, …) means results came from that path.
  - `⚠️ 0 条` means the search worked but nothing matched the window.
  - `❌ …` means the platform failed, with the reason and a fix.
  Relay ❌ reasons briefly; don't hide them.
- A note that a platform's results are "热榜/公开搜索兜底" means those items have **no reliable engagement numbers or dates**. Don't quote engagement for them.
- Never present a failed or empty platform as "nobody is talking about it".

## 6. Login-gated platforms and diagnostics

Since 2025, 微博, 小红书, 知乎 and 抖音 search mostly require a logged-in session. Without one, the engine falls back to hot lists and public web search. When the footer shows they failed or fell back, tell the user the one-time fix:

```bash
python {{SKILL_DIR}}/scripts/last30days.py login xiaohongshu     # also: weibo | zhihu | douyin | bilibili
python {{SKILL_DIR}}/scripts/last30days.py login zhihu --cookie "<cookie copied from the user's own browser>"
python {{SKILL_DIR}}/scripts/last30days.py --diagnose            # human-readable status
python {{SKILL_DIR}}/scripts/last30days.py --diagnose --emit json
python {{SKILL_DIR}}/scripts/last30days.py setup                 # first-time setup + .env template
```

- `login <platform>` opens a visible browser for **the user** to scan a QR code or sign in. Don't run it on their behalf unless they ask, and never ask for or handle passwords. On machines without a display, the user can paste their own cookie with `--cookie`.
- The browser path needs `python -m pip install playwright && python -m playwright install chromium`.
- **Old computers** (e.g. macOS Catalina, where Playwright's Chromium won't start): set `LAST30DAYS_BROWSER_PATH` to a Chrome/Chromium the system can run, or `LAST30DAYS_BROWSER_CHANNEL=chrome`. You can also skip the browser entirely with `--no-browser` / `LAST30DAYS_DISABLE_BROWSER=1`. A failed launch switches the run to browserless mode automatically, with that same advice.

## 7. Synthesis guidance

1. State the date range and which platforms actually returned data.
2. Lead with 跨平台聚合热点 (cross-platform clusters) when present: the same event seen on several platforms is the strongest signal.
3. Compare platform cultures where relevant: 小红书 experience posts vs 知乎 analysis vs 微博 reactions vs B站 tutorials.
4. Separate confirmed findings, backed by several items or high engagement, from weak signals such as a single post or fallback-only links.
5. Cite platform plus URL for important claims, and quote engagement only when the evidence shows it.
6. Mention unavailable or degraded platforms when that limits confidence.
7. Answer in Chinese unless the user asks otherwise.

## Configuration

Everything is optional. Settings go in `~/.config/last30days-cn/.env` (or `.claude/last30days-cn.env` in a project):

```ini
WEIBO_COOKIE=          # or: login weibo
ZHIHU_COOKIE=          # or: login zhihu
BILIBILI_COOKIE=       # reduces Bilibili 412 risk control
TIKHUB_API_KEY=        # Douyin
WECHAT_API_KEY=        # WeChat public accounts (jisuapi)
BAIDU_API_KEY=         # Baidu Qianfan AI Search (Bearer key)
XIAOHONGSHU_API_BASE=  # self-hosted xiaohongshu-mcp, auto-detected on 127.0.0.1:18060
GITHUB_TOKEN=          # higher GitHub search limits
LAST30DAYS_DISABLE_BROWSER=1
```

## Compliance

This skill is for learning, research and personal knowledge work. Keep request frequency low, respect platform terms and robots.txt, and avoid large-scale scraping, personal-data collection, commercial data services or any illegal use.
