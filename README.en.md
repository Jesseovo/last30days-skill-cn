<p align="center">
  <img src="assets/banner.png" alt="last30days-cn — last-30-days research for the Chinese internet" width="900">
</p>

<p align="center">
  <a href="README.md">简体中文</a> ·
  <b>English</b>
</p>

# last30days-cn

**Last-30-days research for the Chinese internet.** Your AI agent checks what people actually said recently on Weibo, Xiaohongshu (RED), Bilibili, Zhihu, Douyin, WeChat public accounts, Baidu and Toutiao. Results are ranked by engagement and recency and merged across platforms into a report where every claim has a source. One command also shows the cross-platform hot-search board.

```bash
npx skills add Jesseovo/last30days-skill-cn -g
```

Then ask your agent:

> Use last30days to research the last 30 days of discussion about the EV price war in China
>
> What's trending on the Chinese internet today?

---

## What it does

- **Topic research**: searches 8 platforms in parallel and scores items by relevance, recency and engagement. The same event seen on several platforms becomes one cross-platform cluster. Output comes as compact evidence for the agent, a full Markdown report, JSON, or an offline HTML report.
- **Hot board**: no topic needed. Collects the Weibo, Baidu, Douyin, Toutiao, Bilibili and Zhihu hot lists and merges cross-platform topics. You can add tech-news RSS and Hacker News, or publish it as a daily web page.
- **Honest coverage**: the report footer lists, per platform, how many items came back and through which data path. A failed platform states the reason and the fix, so missing data never reads as "nobody is talking about it".
- **Reusable logins**: scan a QR code once for platforms that require a login, or import a cookie on machines without a display.
- **Overseas view (optional)**: Hacker News, GitHub, Reddit, plus X, YouTube and TikTok through the original [last30days](https://github.com/mvanhorn/last30days-skill).
- **Lightweight**: Python 3.8+ standard library only; a browser and Chinese word segmentation are optional extras, so it runs on old machines too.

---

## Quick start

**As an agent skill** (Claude Code, Codex, Cursor, Gemini CLI and other Agent Skills hosts):

```bash
npx skills add Jesseovo/last30days-skill-cn -g
```

**From the command line:**

```bash
git clone https://github.com/Jesseovo/last30days-skill-cn.git
cd last30days-skill-cn
python scripts/last30days.py "AI编程助手"      # research a topic
python scripts/last30days.py --hot              # hot board
python scripts/last30days.py --diagnose         # what works and how to fix the rest
```

**Optional extras:**

```bash
python -m pip install jieba                                                  # better Chinese segmentation
python -m pip install playwright && python -m playwright install chromium    # needed for logged-in platforms
```

---

## Usage

### Research a topic

```bash
python scripts/last30days.py "AI编程助手"                       # default: 8 platforms, last 30 days
python scripts/last30days.py "AI编程助手" --emit html-path      # build the HTML report and print its path
python scripts/last30days.py "AI编程助手" --deep                # fetch more per platform
python scripts/last30days.py "AI编程助手" --quick               # only the platforms that best fit the question type
python scripts/last30days.py "AI编程助手" --search bili,zhihu,xhs
python scripts/last30days.py "AI编程助手" --days 7
python scripts/last30days.py "AI编程助手" --as-of 2026-05-01    # look back from a past date
```

Reports are written to `~/.local/share/last30days/out/` (`report.md`, `report.json`, `report.html`, `last30days.context.md`).

### Hot board

```bash
python scripts/last30days.py --hot                                   # Weibo / Baidu / Douyin / Toutiao / Bilibili / Zhihu
python scripts/last30days.py --hot AI                                # only hot items about a theme
python scripts/last30days.py --hot --hot-sources boards,news,global  # + tech-news RSS and Hacker News
python scripts/last30days.py --hot --emit html-path                  # dashboard page
```

Platforms phrase the same event differently, so items are merged by shared key terms and ranked by how many boards they appear on. The page has a keyword filter, dark mode and a phone layout. To add your own feeds, set `LAST30DAYS_HOT_FEEDS="Name|RSS URL,Name|RSS URL"`, e.g. a self-hosted [RSSHub](https://docs.rsshub.app/) route.

### Daily hot-board site

The bundled workflow [`.github/workflows/daily-hot.yml`](.github/workflows/daily-hot.yml) can publish the board as a web page every day. It is **off by default**. To enable it in your repository or fork:

1. Settings → Pages → Source: **GitHub Actions**.
2. Settings → Secrets and variables → Actions → Variables: add `HOT_PAGES` = `true`.
3. Optionally set `HOT_SOURCES` (default `boards,news,global`), `HOT_FEEDS` and `HOT_TITLE`.
4. Actions → **Daily Hot Board** → Run workflow.

It then updates at 08:00, 12:00 and 20:00 Beijing time at `https://<user>.github.io/<repo>/`.

### Platforms that need a login

Search on Xiaohongshu, Weibo, Zhihu and Douyin mostly requires a login. Scan a QR code once (requires Playwright):

```bash
python scripts/last30days.py login xiaohongshu   # also: weibo / zhihu / douyin / bilibili
```

- Sessions are stored in `~/.config/last30days-cn/browser_cookies/`, readable only by you, and reused automatically. You'll be asked to log in again when they expire.
- Without a display (servers, SSH), import a cookie copied from your own browser: `login zhihu --cookie "z_c0=...; _xsrf=..."`.
- You can also set `WEIBO_COOKIE`, `ZHIHU_COOKIE` or `BILIBILI_COOKIE` in the config file.
- Without a login these platforms still return hot-list matches and public web-search results, labelled as "links only, no reliable engagement data".

### Overseas sources (optional)

```bash
python scripts/last30days.py "Claude Code 评测" --global                                # + Hacker News / GitHub / Reddit
python scripts/last30days.py "AI编程助手" --global --global-query "AI coding assistant"  # Chinese topics need English keywords
python scripts/last30days.py "Claude Code" --search x,youtube                            # via upstream last30days
```

- Hacker News, GitHub and Reddit need no keys. `GITHUB_TOKEN` raises GitHub limits; Reddit blocks some cloud IPs and says so clearly.
- X, YouTube, TikTok and Instagram come from a locally installed upstream skill (`npx skills add mvanhorn/last30days-skill -g`, Python 3.12+).
- Off by default. Set `INCLUDE_SOURCES=global` in the config to always include them.

### Old computers and browserless mode

- Bilibili, Toutiao, WeChat, Baidu and the hot board never need a browser.
- If the browser fails to start, the run switches to browserless mode and prints the fix instead of stalling on every platform.
- On old systems (e.g. macOS Catalina) where the bundled Chromium won't start, use an installed browser:

  ```bash
  export LAST30DAYS_BROWSER_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
  python scripts/last30days.py --diagnose --probe-browser    # launch it once to confirm
  ```

- To skip the browser entirely, pass `--no-browser` or set `LAST30DAYS_DISABLE_BROWSER=1`. `LAST30DAYS_BROWSER_CONCURRENCY=1` opens one browser at a time.
- Python 3.8 (the `python3` that ships with macOS Catalina) is supported.

---

## Platforms and data paths

| Platform | Data paths (in order) | Without login / config | Optional config |
|---|---|---|---|
| Weibo | Open API → login-cookie search → logged-in browser | Hot-search match + public web search | `login weibo`, `WEIBO_COOKIE`, `WEIBO_ACCESS_TOKEN` |
| Xiaohongshu | xiaohongshu-mcp → logged-in browser | Public web search (note links only) | `login xiaohongshu`, `XIAOHONGSHU_API_BASE` |
| Bilibili | WBI-signed search → fallback endpoint → browser | ✅ fully works | `BILIBILI_COOKIE` |
| Zhihu | Cookie search → logged-in browser | Hot-list match + public web search | `login zhihu`, `ZHIHU_COOKIE` |
| Douyin | TikHub API → logged-in browser | Hot-list match + public web search | `login douyin`, `TIKHUB_API_KEY` |
| WeChat | jisuapi → Sogou WeChat search | ✅ Sogou works | `WECHAT_API_KEY` |
| Baidu | Qianfan AI Search API → web search | Web search + public web search | `BAIDU_API_KEY` |
| Toutiao | News search + hot board | ✅ fully works | — |
| Overseas (optional) | Hacker News / GitHub / Reddit; upstream bridge for X / YouTube / TikTok | — | `--global`, `GITHUB_TOKEN` |

"Public web search" finds a platform's public pages through search engines. It yields links and snippets only, **without reliable engagement numbers or exact dates**, and the report marks such results.

---

## Configuration

Everything is optional. `python scripts/last30days.py setup` writes a commented template to `~/.config/last30days-cn/.env` (per-project: `.claude/last30days-cn.env`):

```ini
WEIBO_COOKIE=              # or: login weibo
ZHIHU_COOKIE=              # or: login zhihu
BILIBILI_COOKIE=
TIKHUB_API_KEY=            # Douyin
WECHAT_API_KEY=            # WeChat public accounts (jisuapi)
BAIDU_API_KEY=             # Baidu Qianfan AI Search
WEIBO_ACCESS_TOKEN=
XIAOHONGSHU_API_BASE=      # self-hosted xiaohongshu-mcp, auto-detected on 127.0.0.1:18060
GITHUB_TOKEN=
LAST30DAYS_DISABLE_BROWSER=1
INCLUDE_SOURCES=global
EXCLUDE_SOURCES=douyin
LAST30DAYS_HOT_FEEDS=
```

Precedence: process environment > project config > global config.

---

## Command reference

| Flag | Meaning |
|---|---|
| `--emit` | `compact` (default, for agents) / `md` / `json` / `html` / `html-path` / `context` / `path` |
| `--quick` / `--deep` | Faster (platforms chosen by question type) / more results per platform |
| `--days N` / `--as-of YYYY-MM-DD` | Window length (1–30, default 30) / end date for a historical window |
| `--search SOURCES` | Platforms or groups: `weibo`, `xhs`, `bili`, `zhihu`, `douyin`, `wechat`, `baidu`, `toutiao`, `cn`, `global`, `all`, `hn`, `github`, `reddit`, `x`, `youtube`… |
| `--global` / `--global-query Q` | Enable overseas sources / their English query |
| `--hot [keyword]` | Hot board; with `--hot-sources`, `--hot-limit`, `--hot-title` |
| `login <platform> [--cookie "..."]` | Save a platform session |
| `--diagnose [--probe-browser]` | Diagnostics; `--emit json` for machine-readable output |
| `setup` | First-time setup and config template |
| `--no-browser` | Don't use a browser for this run |
| `--refresh` / `--no-cache` / `--cache-ttl H` | Cache control (24 h by default) |
| `--save-dir DIR` / `--timeout SECS` / `--debug` | Save output / global timeout / debug logs |

---

## How it works

1. **Retrieve**: platforms run in parallel, each with its own timeout, so one stuck platform doesn't hold up the rest. Each tries API → login session → public endpoint → public web search, in that order.
2. **Clean**: normalize fields, drop items outside the window, dedupe within a platform, drop off-topic items, keep at most 3 items per author.
3. **Score** (0–100): relevance 45% + recency 25% + engagement 30%. Web-style sources (Baidu, WeChat) use relevance and recency only.
4. **Merge**: the topic's own words are removed before comparing platforms. Otherwise every result would look related just because it mentions the topic.
5. **Output**: compact evidence for the agent to synthesize, plus full report files.

---

## Layout

```
last30days-skill-cn/
├── SKILL.md                 # instructions the agent reads
├── scripts/
│   ├── last30days.py        # CLI entry
│   └── lib/                 # platform adapters, pipeline, hot board, rendering, diagnostics
├── skills/last30days/       # generated installable skill (don't edit by hand)
├── tests/                   # regression tests (no network)
└── .github/workflows/       # CI and the daily hot-board site
```

Contributors: start with [AGENTS.md](AGENTS.md); technical details are in [SPEC.md](SPEC.md); version history is in [release-notes.md](release-notes.md).

---

## ⚠️ Disclaimer

> **Please read carefully. By using this project you agree to all of the terms below.**

1. **For learning and research only.** Commercial use is strictly prohibited.
2. Comply with all applicable laws, including PRC laws on cybersecurity, data security, personal-information protection and unfair competition.
3. Respect each platform's **Terms of Service** and **robots.txt**.
4. **Do NOT** use this project for large-scale or high-frequency scraping; collecting, storing or disseminating personal data; disrupting platform operations; reselling data; or offering automated data-collection services.
5. The developer assumes **no liability**; users bear all legal risk.
6. For infringement concerns, contact the author and it will be addressed promptly.

Browser mode drives a real browser with **your own** logged-in session, and pages issue their own requests. Nothing reverse-engineers encryption or bypasses security mechanisms. Platform interfaces change, and nothing here is guaranteed to keep working. Keep request frequency low (≥ 5 s between searches is a good rule).

---

## Acknowledgements

- [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill): the original project, and the target of the overseas bridge
- [NanmiCoder/MediaCrawler](https://github.com/NanmiCoder/MediaCrawler): inspiration for reusing browser sessions
- [xpzouying/xiaohongshu-mcp](https://github.com/xpzouying/xiaohongshu-mcp): optional Xiaohongshu data service
- [op7418/guizang-ppt-skill](https://github.com/op7418/guizang-ppt-skill): visual style of the HTML report

## License

[MIT](LICENSE). Original project by Matt Van Horn ([mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill)); Chinese localization by Jesse ([@Jesseovo](https://github.com/Jesseovo)).
