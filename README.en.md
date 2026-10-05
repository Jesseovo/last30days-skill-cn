<p align="center">
  <img src="assets/banner.png" alt="last30days-cn — last-30-days research engine for the Chinese internet" width="900">
</p>

<p align="center">
  <a href="README.md">简体中文</a> ·
  <b>English</b>
</p>

# 📰 last30days-cn — last-30-days research for the Chinese internet

> An AI-agent skill that searches what real users said in the **last 30 days** on Weibo, Xiaohongshu (RED), Bilibili, Zhihu, Douyin, WeChat public accounts, Baidu and Toutiao. It ranks results by engagement and recency, clusters the same event across platforms, and writes cited reports. It can also show a **cross-platform hot-search board** in one command.

🔗 A deeply localized fork of [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill).

Current version: **`v4.0.0`** · 👤 Author: Jesse ([@Jesseovo](https://github.com/Jesseovo))

```bash
npx skills add Jesseovo/last30days-skill-cn -g
```

---

## ✨ What's new in v4.0.0

v4 is a major upgrade. Every platform integration was re-verified against live responses in October 2026, with a focus on two old failure modes: silently returning 0 results, and reporting junk links as evidence.

| Area | v3.2 | v4.0 |
|---|---|---|
| Default research run | Often stalled in per-platform timeouts (minutes) | About 10 s measured (browserless, 8 platforms in parallel, each with its own deadline) |
| Bilibili | Truncated UA answered with HTTP 412 by the WAF (#17) | WBI-signed search, buvid3 visitor cookie, complete UA, restricted to the research window |
| Toutiao | Dead endpoint, always 0 results | Parses the cards `so.toutiao.com` renders server-side: titles, source, dates, read/comment/like counts |
| WeChat | Reported Sogou nav links ("图片/知乎/医疗") as articles | Parses only `news-list` result cards, with account name and date |
| Baidu | Called a non-existent API; web results lacked real URLs and dates | Official Qianfan AI Search API; web parser extracts real URL, site, abstract and date, and skips Baidu's own cards and ads |
| Xiaohongshu / Weibo / Zhihu / Douyin | Anonymous requests hit login walls, and users had no way to log in (#8 #11) | New `login <platform>` (QR code once, or `--cookie`). Without a login: hot-list matching plus validated web-search fallback, with the reason and fix command |
| Web-search fallback | Bing only; some regions were redirected to the homepage or got unrelated decoy results | cn.bing → DuckDuckGo → www.bing. Every hit must match the platform's URL pattern and the topic |
| Diagnostics | Platforms reported `true` even when every path was dead | Shows the path each platform will really use, plus login state, browser health and fallback engines |
| Trending | — | `--hot` cross-platform hot board, with an optional daily GitHub Pages site (#16) |
| Overseas sources | — | Opt-in Hacker News / GitHub / Reddit, plus a bridge to upstream last30days for X/YouTube/TikTok (#9) |
| Old computers | Manual browser-path setting only | A failed browser launch switches the run to browserless mode automatically; Python 3.8 (macOS Catalina) support (#13) |

### How each open issue was handled

| Issue | Status | What changed |
|---|---|---|
| [#17](https://github.com/Jesseovo/last30days-skill-cn/issues/17) Bilibili WAF returns 412 for truncated UA | ✅ fixed | Complete browser UAs everywhere (override: `LAST30DAYS_USER_AGENT`); WBI signing + buvid3; on 412 a fresh session retries the legacy endpoint |
| [#16](https://github.com/Jesseovo/last30days-skill-cn/issues/16) A site that only shows today's hot topics | ✅ shipped | `--hot` plus `.github/workflows/daily-hot.yml`, which publishes to GitHub Pages three times a day once enabled. Custom RSS (e.g. RSSHub) covers VC/tech news and X lists |
| [#13](https://github.com/Jesseovo/last30days-skill-cn/issues/13) 2012 MacBook Pro (Catalina) | ✅ improved | Browserless mode is first-class; automatic circuit breaker; Python 3.8 support; `--diagnose --probe-browser` tests a real launch |
| [#11](https://github.com/Jesseovo/last30days-skill-cn/issues/11) XHS XHR now only returns suggestions | ✅ fixed | Three parsers (XHR note cards → `__INITIAL_STATE__` → DOM), a login entry point, the correct xiaohongshu-mcp contract (`POST /api/v1/feeds/search`), and `xsec_token` in note links |
| [#10](https://github.com/Jesseovo/last30days-skill-cn/issues/10) `npx` install: File name too long | ✅ fixed in v3.0 | No symlinks remain (regression test); `.gitattributes` now pins LF endings |
| [#9](https://github.com/Jesseovo/last30days-skill-cn/issues/9) Keep the overseas platforms | ✅ opt-in | Off by default. `--global` enables key-free HN / GitHub / Reddit; X/YouTube/TikTok come from an installed upstream last30days instead of duplicating its adapters here |
| [#8](https://github.com/Jesseovo/last30days-skill-cn/issues/8) XHS Playwright returns nothing | ✅ improved | Root cause: no login session. `login xiaohongshu` fixes it, `--diagnose` reports login state honestly, and Zhihu/Douyin/Toutiao from the comments are handled too |

Full changelog: [release-notes.md](release-notes.md).

---

## 🚀 Quick start

```bash
npx skills add Jesseovo/last30days-skill-cn -g
# then ask your agent: "use last30days to research AI coding assistants" / "what's trending in China today?"
```

Or run the CLI directly (Python 3.8+, **no required dependencies**):

```bash
git clone https://github.com/Jesseovo/last30days-skill-cn.git && cd last30days-skill-cn
python scripts/last30days.py "AI编程助手"                  # topic research
python scripts/last30days.py "AI编程助手" --emit html-path # offline HTML report
python scripts/last30days.py --hot                         # cross-platform hot board
python scripts/last30days.py --diagnose                    # what works and how to fix the rest
```

Optional extras: `pip install jieba` (better Chinese segmentation), and `pip install playwright && python -m playwright install chromium` (needed for logged-in platforms).

---

## 🔥 Hot board and a daily "just the trends" site (#16)

```bash
python scripts/last30days.py --hot                                  # Weibo/Baidu/Douyin/Toutiao/Bilibili/Zhihu (~3 s)
python scripts/last30days.py --hot AI                               # only hot items about AI
python scripts/last30days.py --hot --hot-sources boards,news,global # + tech-news RSS and Hacker News
python scripts/last30days.py --hot --emit html-path                 # dashboard page
```

- **Cross-platform topics**: platforms phrase the same event differently, so items are merged by IDF-weighted salient terms and ranked by how many boards they appear on. Pinned editorial items are excluded.
- **Custom feeds**: `LAST30DAYS_HOT_FEEDS="Name|https://rsshub.example/...,..."`, e.g. a self-hosted RSSHub route for 36Kr newsflashes or an X list.
- **Publish it**: the bundled `.github/workflows/daily-hot.yml` is off by default. To turn it on:
  1. Set Pages → Source to **GitHub Actions**.
  2. Add the repository variable `HOT_PAGES=true`.
  3. Optionally set `HOT_SOURCES`, `HOT_FEEDS` and `HOT_TITLE`.
  4. Run **Daily Hot Board**.

  It then updates at 08:00/12:00/20:00 Beijing time.

## 🔐 Logged-in platforms

Since 2025, Xiaohongshu, Weibo, Zhihu and Douyin search largely require a login.

- `python scripts/last30days.py login xiaohongshu` (also `weibo|zhihu|douyin|bilibili`) opens a browser; scan the QR code once. The session is saved with 0600 permissions and reused by headless runs.
- On machines without a display, import your own browser cookie: `login zhihu --cookie "z_c0=..."`.
- Alternatively set `WEIBO_COOKIE` / `ZHIHU_COOKIE` / `BILIBILI_COOKIE` in `.env`.

## 🌏 Overseas sources (opt-in, #9)

```bash
python scripts/last30days.py "Claude Code 评测" --global
python scripts/last30days.py "AI编程助手" --global --global-query "AI coding assistant"   # Chinese topic → English query
python scripts/last30days.py "Claude Code" --search x,youtube                            # via the upstream bridge
```

- Hacker News (Algolia), GitHub (optional `GITHUB_TOKEN`) and Reddit (often 403 from cloud IPs, reported clearly) need no keys.
- X/YouTube/TikTok/Instagram run through an installed `mvanhorn/last30days` (Python 3.12+; `LAST30DAYS_UPSTREAM`, `LAST30DAYS_UPSTREAM_PYTHON`).

## 💻 Old computers / browserless mode (#13)

- Bilibili, Toutiao, WeChat, Baidu and all hot boards work without a browser. Login-gated platforms fall back to hot-list matching and web search.
- One failed browser launch disables browser paths for the rest of the run, with fix advice.
- Use a system browser with `LAST30DAYS_BROWSER_PATH=/Applications/Google Chrome.app/Contents/MacOS/Google Chrome` or `LAST30DAYS_BROWSER_CHANNEL=chrome`, then verify with `--diagnose --probe-browser`.
- Skip the browser entirely with `--no-browser` / `LAST30DAYS_DISABLE_BROWSER=1`. Limit parallel browsers with `LAST30DAYS_BROWSER_CONCURRENCY=1`.
- Python 3.8 is supported and tested in CI.

---

## 📋 Platforms and data paths

| Platform | Primary paths (in order) | Without login/key | Optional config |
|---|---|---|---|
| Weibo | Open API → login-cookie search → logged-in browser | Hot-search match + web-search fallback | `WEIBO_COOKIE`, `login weibo`, `WEIBO_ACCESS_TOKEN` |
| Xiaohongshu | xiaohongshu-mcp → logged-in browser (XHR / page state / DOM) | Web-search fallback (note links only) | `login xiaohongshu`, `XIAOHONGSHU_API_BASE` |
| Bilibili | WBI search in the window → legacy endpoint → browser | ✅ fully works | `BILIBILI_COOKIE` |
| Zhihu | Cookie search → logged-in browser | Hot-list match + web-search fallback | `ZHIHU_COOKIE`, `login zhihu` |
| Douyin | TikHub → logged-in browser (page signs its own requests) | Hot-list match + web-search fallback | `TIKHUB_API_KEY`, `login douyin` |
| WeChat | jisuapi → Sogou WeChat | ✅ Sogou works | `WECHAT_API_KEY` |
| Baidu | Qianfan AI Search API → web search | Web search (may hit captcha) + multi-engine fallback | `BAIDU_API_KEY` |
| Toutiao | so.toutiao.com search + hot board | ✅ fully works | — |
| Overseas (opt-in) | Hacker News / GitHub / Reddit; upstream bridge for X/YouTube/TikTok | — | `--global`, `GITHUB_TOKEN`, `LAST30DAYS_UPSTREAM` |

> Web-search fallback items are public links **without reliable engagement or exact dates**. Reports label them, and the agent is told not to quote engagement for them.

## ⚙️ Configuration

Everything is optional. `python scripts/last30days.py setup` writes a commented template at `~/.config/last30days-cn/.env` (per project: `.claude/last30days-cn.env`). Runtime switches such as `LAST30DAYS_DISABLE_BROWSER`, `INCLUDE_SOURCES` and `EXCLUDE_SOURCES` now work from that file too.

## 🧭 CLI

| Flag | Meaning |
|---|---|
| `--emit` | `compact` (default, for agents) / `md` / `json` / `html` / `html-path` / `context` / `path` |
| `--quick` / `--deep` | Faster (query-type tiered platforms) / more pages per platform |
| `--days N` / `--as-of YYYY-MM-DD` | Window length (1–30) / historical end date |
| `--search SOURCES` | Ids, aliases or groups: `weibo,xhs,bili,zhihu,douyin,wechat,baidu,toutiao`, `cn`, `global`, `all`, `hn`, `github`, `reddit`, `x`, `youtube`… |
| `--global` / `--global-query Q` | Enable overseas sources / their English query |
| `--hot [keyword]`, `--hot-sources`, `--hot-limit`, `--hot-title` | Hot board |
| `login <platform> [--cookie "..."]` | Save a platform session |
| `--diagnose [--probe-browser] [--emit json]` | Diagnostics |
| `--no-browser`, `--refresh`, `--no-cache`, `--cache-ttl`, `--save-dir`, `--timeout`, `--debug` | Misc |

Outputs go to `~/.local/share/last30days/out/` (`report.md/json/html`, `last30days.context.md`, `hot.md/json/html`); override with `LAST30DAYS_OUTPUT_DIR`.

## 📊 Ranking

Score (0–100) = **relevance 45% + recency 25% + engagement 30%**; web-style sources (Baidu, WeChat) use relevance and recency only. Dated items outside the window are dropped. Near-duplicates and pure noise are removed, with at most 3 items per author. Cross-platform clustering ignores the query's own words, since every result contains them.

## 🏗️ Layout

`SKILL.md` and `scripts/` are the sources of truth; `skills/last30days/` is the generated installable payload (`python scripts/build_payload.py`). Key modules: `sources.py` (registry), `pipeline.py`, `http.py`, `websearch.py`, `crawler_bridge.py`, the platform adapters, `trending.py`, `render.py`, `doctor.py`. See [SPEC.md](SPEC.md).

---

## ⚠️ Disclaimer

> **Please read carefully. By using this project you agree to all of the terms below.**

1. **This project is for learning and research only.** Commercial use is strictly prohibited.
2. Users must comply with all applicable laws and regulations, including PRC laws on cybersecurity, data security, personal-information protection and unfair competition.
3. Users must respect each platform's **Terms of Service** and **robots.txt**.
4. **Do NOT** use this project for large-scale or high-frequency scraping; collecting, storing or disseminating personal data; disrupting platform operations; reselling data; or providing automated data-collection services.
5. The developer assumes **no liability** for any consequences of using this project; users bear all legal risk.
6. For infringement concerns, contact the author and it will be addressed promptly.

Browser mode drives a real browser with **your own** logged-in session; pages issue their own requests. Nothing reverse-engineers encryption or bypasses security mechanisms. Platform interfaces change; keep request frequency low (e.g. ≥ 5 s between searches).

## 🙏 Acknowledgements

[mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill) · [NanmiCoder/MediaCrawler](https://github.com/NanmiCoder/MediaCrawler) · [xpzouying/xiaohongshu-mcp](https://github.com/xpzouying/xiaohongshu-mcp) · [op7418/guizang-ppt-skill](https://github.com/op7418/guizang-ppt-skill)

## 📜 License

[MIT](LICENSE) · Original project by Matt Van Horn · Chinese localization by Jesse ([@Jesseovo](https://github.com/Jesseovo))
