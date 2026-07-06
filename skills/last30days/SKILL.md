---
name: last30days-cn
version: "3.1.0-cn"
description: "Chinese-platform last-30-days research skill covering Weibo, Xiaohongshu, Bilibili, Zhihu, Douyin, WeChat, Baidu, and Toutiao. Includes Markdown, JSON, compact context, and Guizang-inspired Swiss/IKB HTML report output."
argument-hint: 'last30 AI 编程助手, last30 最近 30 天中文平台舆情, last30 具身智能 --html'
allowed-tools: Bash, Read, Write, WebSearch
author: Jesse
license: MIT
user-invocable: true
metadata:
  openclaw:
    emoji: "CN"
    requires:
      optionalEnv:
        - WEIBO_ACCESS_TOKEN
        - SCRAPECREATORS_API_KEY
        - ZHIHU_COOKIE
        - TIKHUB_API_KEY
        - DOUYIN_API_KEY
        - WECHAT_API_KEY
        - BAIDU_API_KEY
        - BAIDU_SECRET_KEY
      bins:
        - python3
    files:
      - "scripts/*"
    tags:
      - research
      - deep-research
      - chinese-platforms
      - weibo
      - xiaohongshu
      - bilibili
      - zhihu
      - douyin
      - wechat
      - baidu
      - toutiao
      - trends
      - html-report
---

# last30days-cn

You are a Chinese-platform research assistant. Use this skill when the user asks for recent Chinese internet discussion, trend research, public-source evidence, or "last 30 days" coverage across Weibo, Xiaohongshu, Bilibili, Zhihu, Douyin, WeChat public accounts, Baidu, and Toutiao.

## Core Rule

Always ground claims in returned results. Do not invent sources, links, engagement numbers, dates, or platform sentiment. If coverage is sparse, say so clearly.

## Run

Use the skill-local scripts directory:

```bash
python {{SKILL_DIR}}/scripts/last30days.py "{{USER_TOPIC}}" --emit compact
```

Useful variants:

```bash
python {{SKILL_DIR}}/scripts/last30days.py "{{USER_TOPIC}}" --quick --emit compact
python {{SKILL_DIR}}/scripts/last30days.py "{{USER_TOPIC}}" --deep --emit md
python {{SKILL_DIR}}/scripts/last30days.py "{{USER_TOPIC}}" --emit html-path
python {{SKILL_DIR}}/scripts/last30days.py "{{USER_TOPIC}}" --search weibo,bilibili,zhihu --emit compact
python {{SKILL_DIR}}/scripts/last30days.py "{{USER_TOPIC}}" --as-of 2026-05-01 --emit compact
python {{SKILL_DIR}}/scripts/last30days.py "{{USER_TOPIC}}" --refresh --emit compact
python {{SKILL_DIR}}/scripts/last30days.py "{{USER_TOPIC}}" --no-cache --emit compact
python {{SKILL_DIR}}/scripts/last30days.py --diagnose
python {{SKILL_DIR}}/scripts/last30days.py --diagnose --emit json
python {{SKILL_DIR}}/scripts/last30days.py setup
```

`--as-of YYYY-MM-DD` 以指定日期为终点回溯 N 天（历史回溯）；`--refresh` 忽略缓存并刷新结果；`--no-cache` 跳过缓存读写；`--cache-ttl HOURS` 控制缓存有效期。未指定 `--search` 时回退到环境变量 `LAST30DAYS_DEFAULT_SEARCH`，`EXCLUDE_SOURCES` 可排除指定源。输出中若多个平台讨论同一事件，会先给出「跨平台聚合热点」。

## 输出契约

- Preserve the first engine badge line exactly, e.g. `🌐 last30days-cn v... · 数据截至 ...`; if it ends with `· 缓存`, mention that the evidence is cached.
- Do not invent a new title before the badge and do not add a final `Sources:` block. Cite sources inline with platform names and URLs from the returned evidence.
- Do not invent source availability, engagement numbers, dates, or cross-platform sentiment. If a source is unavailable or sparse, say that directly.
- Treat `--diagnose` text as human-readable setup guidance; use `--diagnose --emit json` only when machine-readable status is needed.

## Output Modes

- `compact`: concise Markdown evidence for the agent to synthesize.
- `md`: full Markdown report.
- `html`: complete standalone HTML report.
- `html-path`: path to the generated `report.html`.
- `json`: structured report data.
- `context`: reusable context snippet.
- `path`: path to `last30days.context.md`.

The HTML report uses a Swiss/IKB visual system inspired by `op7418/guizang-ppt-skill`. It is intended for browser viewing, archiving, and printing, not for interactive PPT generation.

## 查询类型路由提示

- Breaking news, hot debates, or public sentiment: prioritize Weibo and Toutiao, with Baidu for cross-checking.
- Tutorials, workflows, demos, or creator tools: prioritize Bilibili, Xiaohongshu, Zhihu, and WeChat.
- Product reputation or recommendation questions: compare Xiaohongshu, Zhihu, Bilibili, and Weibo rather than relying on one platform.
- When the topic is broad or ambiguous, run the default source set and synthesize only claims supported by returned evidence.

## Configuration

Most sources can be tried with no configuration. Optional credentials improve stability:

```ini
WEIBO_ACCESS_TOKEN=
SCRAPECREATORS_API_KEY=
ZHIHU_COOKIE=
TIKHUB_API_KEY=
DOUYIN_API_KEY=
WECHAT_API_KEY=
BAIDU_API_KEY=
BAIDU_SECRET_KEY=
```

Config file:

```text
~/.config/last30days-cn/.env
```

Optional crawler mode:

```bash
python -m pip install playwright
python -m playwright install chromium
```

First-time setup helper:

```bash
python {{SKILL_DIR}}/scripts/last30days.py setup
```

## Synthesis Guidance

When presenting the final answer:

1. State the date range and the active sources.
2. Separate confirmed findings from weak or sparse signals.
3. Cite platform and URL for important claims.
4. Compare platform differences when multiple sources discuss the same topic.
5. Mention unavailable or failed sources if that affects confidence.
6. Keep the final answer in Chinese unless the user requests otherwise.

## Compliance

This skill is for learning, research, and personal knowledge work. Use low frequency, respect platform terms and robots.txt, and avoid large-scale scraping, personal data collection, commercial collection services, or any illegal use.
