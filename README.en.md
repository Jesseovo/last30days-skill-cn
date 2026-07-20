<p align="center">
  <img src="assets/banner.png" alt="last30days-cn — Chinese Platform Deep Research Engine" width="900">
</p>

<p align="center">
  <a href="README.md">简体中文</a> ·
  <b>English</b>
</p>

# 📰 last30days-cn — Chinese Platform Deep Research Engine

> 🚀 30 days of research, 30 seconds of work. 8 platforms. Zero stale info.

**last30days-cn** is an AI Agent skill that automatically searches the 8 major Chinese internet platforms for the last 30 days of content and generates well-cited research reports.

🔗 This project is a deeply localized fork of [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill), fully adapted for Chinese users and Chinese internet platforms.

🕷️ v2.0 integrates the [MediaCrawler](https://github.com/NanmiCoder/MediaCrawler) crawler-engine approach to greatly reduce API-key dependency. v2.1 fixed Baidu/Xiaohongshu anti-bot issues (XHR interception over DOM parsing, Bing search fallback) and removed the ineffective ScrapeCreators Xiaohongshu integration.

Current version: `v3.2.0`

👤 **Author:** Jesse ([@Jesseovo](https://github.com/Jesseovo))

---

## ✨ What's new in v3.2.0

- Fixed the new Xiaohongshu search flow: `search/recommend` suggestions (`sug_items`) are no longer mistaken for note results, and the crawler can submit the search box when the page does not auto-run the query.
- Xiaohongshu response parsing now recognizes note-card payloads instead of depending on one endpoint path.
- Added an old-machine browser mode: use `LAST30DAYS_BROWSER_PATH` for a system-supported Chromium/Chrome, or set `LAST30DAYS_DISABLE_BROWSER=1` to force public API/search fallbacks.
- `--diagnose` reports the browser mode and configured external browser path.
- Version is now `v3.2.0`; the installable payload remains checked against the root sources.

## ✨ What's new in v3.0.0

- Matches upstream v3's Agent Skills package layout: `skills/last30days` is now an independently installable runtime payload.
- The Chinese CLI uses a single entry point, `last30days.py`, with the same structure in both the repo root and the skill payload.
- Added `--emit html` and `--emit html-path` to generate an offline-openable `report.html`.
- The HTML report adopts the Swiss/IKB visual language from [op7418/guizang-ppt-skill](https://github.com/op7418/guizang-ppt-skill) — good for browsing, archiving, and printing.
- Xiaohongshu and Zhihu search now report empty-result fallbacks, listing which paths were tried and likely causes on failure.
- Douyin and Toutiao now fall back to a public search engine when their native APIs are rate-limited, so they no longer silently return 0 results (see issue #8).
- Fixed `npx` install failure on macOS/Linux caused by a corrupted symlink at `skills/last30days/SKILL.md` (see issue #10).
- Synced several platform-agnostic capabilities from upstream [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill): `--as-of` historical lookback, cross-source cluster merging, `LAST30DAYS_DEFAULT_SEARCH`/`EXCLUDE_SOURCES` config knobs, honest `--diagnose` (live probes), and HTML report XSS hardening.
- The repo-root `scripts/` is kept for local development and legacy paths; Agent Skills installs use the self-contained payload under `skills/last30days/scripts`.

### ✅ Release checks

Done before this release:

- The published remote tag is unified as `v3.2.0`, with no extra v3-derived tags.
- Both the repo root and the skill payload use the single `last30days.py` entry point — no extra entry files.
- Full test suite passes: `python -m pytest tests -q`, `214 passed`.
- Both entry points verified: `py scripts/last30days.py --diagnose` and `py skills/last30days/scripts/last30days.py --diagnose` both print platform availability diagnostics.

---

## ⚠️ Disclaimer

> **Please read carefully. By using this project you agree to all of the terms below.**

1. **This project is for learning and research only.** All crawler features are intended solely for technical study and exchange; **commercial use is strictly prohibited.**
2. Users must comply with all applicable laws and regulations (data security, personal-information protection, anti-unfair-competition, etc.).
3. Users must respect each platform's **Terms of Service (ToS)** and **robots.txt**.
4. **Do NOT** use this project for: large-scale / high-frequency scraping; collecting, storing, or disseminating others' personal data; disrupting platform operations; reselling data or any commercial gain; or providing automated data-collection services to third parties.
5. The developer assumes **no liability** for any legal consequences arising from use of this project. Users bear **all** legal risk themselves.
6. For any infringement concerns, contact the author and it will be addressed promptly.

### Technical notes

- The crawler features rely on Playwright browser automation to mimic normal browsing; they do **not** reverse-engineer encryption or break security mechanisms.
- Platform interfaces can change at any time; this project does not guarantee that every feature always works.
- Keep request frequency reasonable (e.g. ≥ 5s between searches) to avoid being blocked.

> 💡 **Illegal scraping cases are common — use this lawfully and compliantly.**
> Reference: [Chinese crawler legal cases](https://github.com/HiddenStrawberry/Crawler_Illegal_Cases_In_China)

---

## 📋 Platform support

| Platform | Module | Data sources | Configuration |
|:---:|:---:|:---:|:---:|
| 🔴 Weibo | `weibo.py` | API / 🕷️ crawler / public API | ✅ No config in crawler mode |
| 📕 Xiaohongshu | `xiaohongshu.py` | API / 🕷️ crawler / public API / search fallback | ✅ No config in crawler mode |
| 📺 Bilibili | `bilibili.py` | Public API / 🕷️ crawler backup | ✅ No config |
| 💬 Zhihu | `zhihu.py` | Public search / 🕷️ crawler backup / search fallback | ✅ No config |
| 🎵 Douyin | `douyin.py` | API / 🕷️ crawler / public API / search fallback | ✅ No config in crawler mode |
| 💚 WeChat | `wechat.py` | API / Sogou search | `WECHAT_API_KEY` (optional) |
| 🔵 Baidu | `baidu.py` | Public search / API | ✅ No config for basic search |
| 📰 Toutiao | `toutiao.py` | Public API / search fallback | ✅ No config |

> 🕷️ = requires Playwright (`pip install playwright && playwright install chromium`)

---

## 🤖 Install

| Surface | Install |
|:---|:---|
| **Agent Skills (recommended)** | `npx skills add Jesseovo/last30days-skill-cn -g` |
| **Claude Code** | `npx skills add Jesseovo/last30days-skill-cn -g` |
| **Cursor** | Clone the repo and add `SKILL.md` as a project skill |
| **OpenClaw / ClawHub** | `git clone https://github.com/Jesseovo/last30days-skill-cn.git ~/.agents/skills/last30days-cn` |
| **Gemini CLI** | Clone and load as a Gemini extension |
| **Any agent** | Any AI agent with **Bash / Read / Write** tools |

### Agent Skills (recommended)

```bash
npx skills add Jesseovo/last30days-skill-cn -g
```

### Manual (developer)

```bash
git clone https://github.com/Jesseovo/last30days-skill-cn.git ~/.claude/skills/last30days-cn
```

---

## ⚙️ Configuration

### Step 1 — Optional enhancements

```bash
python -m pip install jieba
```

> `jieba` is optional. Without it, the skill automatically falls back to CJK bigram tokenization.

### Step 2 — Install the crawler engine (optional, recommended; enables 7/8 platforms without API keys)

```bash
python -m pip install playwright
python -m playwright install chromium
```

> With Playwright installed, Weibo, Xiaohongshu, Douyin, Bilibili (backup), and Zhihu (backup) all work without API keys.

### Older macOS / older computers

If the Playwright-managed Chromium build no longer starts on an older system such as macOS Catalina, point Playwright at a browser that still supports that system:

```bash
export LAST30DAYS_BROWSER_PATH="/Applications/Chromium.app/Contents/MacOS/Chromium"
python scripts/last30days.py --diagnose
```

Alternatively use an installed Chrome channel with `LAST30DAYS_BROWSER_CHANNEL=chrome`, or force browserless public fallbacks with `LAST30DAYS_DISABLE_BROWSER=1`. The configured browser must already be compatible with the operating system; this project does not download or upgrade it.

### Step 3 — Create a config file (optional)

For more stable API-mode data, or to use WeChat public-account search:

```bash
mkdir -p ~/.config/last30days-cn
touch ~/.config/last30days-cn/.env
chmod 600 ~/.config/last30days-cn/.env
```

**Windows (PowerShell):** create the config directory with `New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.config\last30days-cn"`, then create the file with `New-Item -ItemType File -Path "$env:USERPROFILE\.config\last30days-cn\.env" -Force` (or edit `%USERPROFILE%\.config\last30days-cn\.env`). To restrict `.env` to the current user (similar intent to `chmod 600`; the ACL model differs), run `icacls "$env:USERPROFILE\.config\last30days-cn\.env" /inheritance:r /grant:r "$($env:USERNAME):(R,W)"`.

Edit `~/.config/last30days-cn/.env` and fill in API keys as needed (all optional):

```ini
# All API keys are OPTIONAL. With Playwright installed, most platforms
# already work via crawler mode; API keys just give more stable data.

WEIBO_ACCESS_TOKEN=      # Weibo Open Platform (optional; crawler covers it)
SCRAPECREATORS_API_KEY=  # Xiaohongshu (optional; crawler covers it)
ZHIHU_COOKIE=            # Zhihu cookie (optional; improves search quality)
TIKHUB_API_KEY=          # Douyin (optional; crawler covers it)
WECHAT_API_KEY=          # WeChat public accounts (no crawler alternative; required for WeChat)
BAIDU_API_KEY=           # Baidu Search API (optional; public search already works)
BAIDU_SECRET_KEY=
```

### Step 4 — Verify

```bash
python scripts/last30days.py --diagnose
```

Prints each platform's availability plus crawler-engine status:

```json
{
  "weibo": true,
  "xiaohongshu": false,
  "bilibili": true,
  "zhihu": true,
  "douyin": true,
  "wechat": false,
  "baidu_api": false,
  "toutiao": true,
  "crawler_engine": {
    "playwright_available": true,
    "cached_logins": [],
    "note": "With Playwright installed, Weibo/Xiaohongshu/Douyin/Bilibili/Zhihu work without API keys"
  },
  "note_douyin_toutiao": "Douyin/Toutiao native APIs require signature params and are often rate-limited; on failure they fall back to a public search engine, which only yields public links (no real engagement data or precise dates)."
}
```

---

## 🚀 Usage

### Basic

```bash
python scripts/last30days.py "AI coding assistant" --emit compact
python scripts/last30days.py "AI coding assistant" --emit html-path
```

### CLI flags

| Flag | Description | Example |
|:---:|:---:|:---:|
| `--emit` | Output mode | `compact` / `json` / `md` / `context` / `path` / `html` / `html-path` |
| `--quick` | Quick search | Fewer sources, faster |
| `--deep` | Deep search | More sources, more thorough |
| `--days N` | Look-back days | `--days 7` (last week) |
| `--as-of` | Historical end date | `--as-of 2026-05-01` (look back N days from that date) |
| `--search` | Specific sources | `--search weibo,bilibili,zhihu` |
| `--diagnose` | Diagnose config | Show per-platform availability |
| `--timeout SECS` | Global timeout | Override the default global timeout |
| `--save-dir DIR` | Auto-save raw output | Write raw output to the given dir |
| `--debug` | Debug mode | Verbose logging |

> 🔧 **Env vars**: when `--search` is omitted, it falls back to `LAST30DAYS_DEFAULT_SEARCH` (a comma-separated default source set); `EXCLUDE_SOURCES` removes sources from the active set.

### Examples

```bash
# 🔍 Search an AI topic
python scripts/last30days.py "latest AI tools" --emit compact

# ⚡ Quick search, Bilibili + Zhihu only
python scripts/last30days.py "Python tutorial" --quick --search bilibili,zhihu

# 📊 Deep search and save results
python scripts/last30days.py "EV cars" --deep --save-dir ~/Documents/research

# 📋 JSON output (for programmatic use)
python scripts/last30days.py "ChatGPT alternatives" --emit json

# 🗓️ Last 7 days only
python scripts/last30days.py "trending topics" --days 7

# 🧾 Generate an offline-openable HTML report
python scripts/last30days.py "embodied AI" --deep --emit html-path
```

---

## 🔧 Data-fetching strategy (tiered fallback)

```
Tier 1: API mode (if an API key is configured)
    ↓ failed or not configured
Tier 2: Crawler mode (MediaCrawler, requires Playwright)
    ↓ failed or not installed
Tier 3: Public API (direct HTTP, no config needed)
    ↓ still no results (Douyin / Toutiao / Xiaohongshu / Zhihu)
Fallback: Public search engine (Bing `site:` search, yields public links)
```

> ⚠️ Douyin/Toutiao native web APIs now require signature params (`a_bogus` / `_signature`) and are often rate-limited. On failure they fall back to a public search engine, which **only yields public links — no real engagement data or precise dates.**

---

## 🏗️ Project layout

```
last30days-skill-cn/
├── SKILL.md              # Agent skill definition
├── README.md             # Docs (Chinese)
├── README.en.md          # Docs (English, this file)
├── LICENSE               # MIT license
├── requirements.txt      # Python deps
├── assets/               # README images
├── scripts/              # Dev copy: last30days.py + lib/ (per-platform modules)
├── skills/last30days/    # Self-contained Agent Skills payload (SKILL.md + scripts/)
├── fixtures/             # Sample data
├── tests/                # Test cases
└── hooks/                # Agent hooks
```

---

## 📊 Scoring

Each result gets a 0–100 composite score:

| Dimension | Weight | Notes |
|:---:|:---:|:---|
| 🎯 Relevance | 45% | Text match against the query |
| 🕐 Recency | 25% | Freshness of the publish time |
| 🔥 Engagement | 30% | Per-platform interaction metrics |

---

## 🙏 Acknowledgements

- [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill) — the original English project
- [NanmiCoder/MediaCrawler](https://github.com/NanmiCoder/MediaCrawler) — crawler-engine inspiration

---

## 📜 License

Released under the [MIT License](LICENSE).

- 🔗 Original: [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill) by Matt Van Horn
- 🇨🇳 Chinese fork: Jesse ([@Jesseovo](https://github.com/Jesseovo))
