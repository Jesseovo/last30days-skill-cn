# last30days-cn 技术规格说明（v4）

> Author: Jesse (https://github.com/Jesseovo)

## 概述

**last30days-cn** 是一条面向中文互联网的多源研究流水线。给定主题后：

1. `lib/pipeline.py` 在研究时间窗（默认 30 天，按北京时间计）内并行调用各平台适配器（守护线程，每个源有独立截止时间）。
2. 原始条目经 `normalize` 归一为统一 schema，再经时间窗过滤、打分（相关性/时效/互动）、排序、同源去重、相关性门槛、单作者上限处理。
3. 去掉主题词后做跨源关联（`cross_refs`）与跨平台聚类（`clusters`）。
4. 输出 `compact` / `md` / `json` / `html` / `context`，并写入 `report.md`、`report.json`、`report.html`、`last30days.context.md`。

另有两个独立模式：

- **全网热榜** `--hot`（`lib/trending.py`）：抓取各平台热榜，按显著词合并跨平台热点。
- **登录** `login <平台>`（`lib/crawler_bridge.py`）：保存浏览器登录态。

运行时只依赖 Python 3.8+ 标准库；`jieba`（分词）与 `playwright`（浏览器）为可选增强。

---

## 数据源注册表（`lib/sources.py`）

| id | 标签 | ID 前缀 | 分组 | 别名 |
|---|---|---|---|---|
| weibo | 微博 | WB | cn | wb |
| xiaohongshu | 小红书 | XHS | cn | xhs, rednote, red |
| bilibili | B站 | BL | cn | bili, b站 |
| zhihu | 知乎 | ZH | cn | zh |
| douyin | 抖音 | DY | cn | dy |
| wechat | 微信公众号 | WX | cn | weixin, wx, mp |
| baidu | 百度 | BD | cn | bd |
| toutiao | 今日头条 | TT | cn | tt |
| hackernews | Hacker News | HN | global（默认关） | hn |
| github | GitHub | GH | global（默认关） | gh |
| reddit | Reddit | RD | global（默认关） | rd |
| upstream | 海外平台（上游桥接） | UP | global（默认关） | x, twitter, youtube, tiktok, instagram, last30days |

分组：`cn`（8 个中文平台）、`global`（hackernews/github/reddit）、`all`（两者合计）。

默认选源：
- 未指定 `--search` 时运行全部中文平台；`--quick` 时按查询类型分层（`query_type.SOURCE_TIERS`）。
- 之后并上 `INCLUDE_SOURCES` / `--global`，再减去 `EXCLUDE_SOURCES`。

---

## 平台适配器

| 模块 | 数据路径（按顺序） | 备注 |
|---|---|---|
| `weibo.py` | 开放平台 API → `WEIBO_COOKIE` 移动端搜索 → 登录态浏览器 → 访客 Cookie → 热搜榜匹配 + 公开搜索 | 匿名搜索返回 `ok=-100` 时抛出 `WeiboLoginRequired` |
| `xiaohongshu.py` | xiaohongshu-mcp `POST /api/v1/feeds/search` → 浏览器（XHR / `__INITIAL_STATE__` / DOM）→ 公开搜索（`/explore/<24位ID>`） | 笔记链接带 `xsec_token` |
| `bilibili.py` | WBI 签名 `/x/web-interface/wbi/search/type`（buvid3、时间窗）→ 旧版接口 → 浏览器 | 412/-412/-352 视为风控 |
| `zhihu.py` | search_v3（仅在有 Cookie 时）→ 浏览器拦截 search_v3 → 热榜匹配 → 公开搜索 | |
| `douyin.py` | TikHub → 浏览器拦截搜索 XHR → 热榜匹配 → 公开搜索 | |
| `wechat.py` | 极速数据 API → 搜狗微信 `news-list` → `site:mp.weixin.qq.com` | |
| `baidu.py` | 千帆 AI 搜索 `web_search` → 百度网页（`mu`、站点、日期）→ 多引擎搜索 | 跳过 `result-op` 卡片与广告 |
| `toutiao.py` | `so.toutiao.com` 服务端渲染的 JSON 卡片 → 热榜匹配 → 公开搜索 | 遇到空页面壳会重试 |
| `hackernews.py` | Algolia 搜索（时间窗） | 需要英文检索词 |
| `github.py` | 仓库（`pushed:` 时间窗）+ Issue/PR（`created:` 时间窗） | 可选 `GITHUB_TOKEN` |
| `reddit.py` | 公开 `search.json` | 数据中心 IP 常被 403 |
| `upstream_bridge.py` | 子进程运行上游 `last30days.py --emit json --json-profile raw` | 映射 `items_by_source` |

每个适配器都返回带 `source` 字段（数据路径）的 dict 列表，失败时抛出 `http.HTTPError` 并附带可读原因与修复建议。

---

## 公共模块

| 模块 | 职责 |
|---|---|
| `http.py` | 完整浏览器 UA / client hints（`browser_headers`）、gzip/deflate + 字符集解码、`Session`（Cookie）、`fetch()`（返回最终 URL）、重试与 Retry-After、412 快速失败、调试日志脱敏 |
| `websearch.py` | 多引擎公开搜索（cn.bing / DuckDuckGo / www.bing）、跳转链接解析、节流、引擎拦截记忆、URL 规则 + 相关性校验 |
| `crawler_bridge.py` | Playwright 启动（外部浏览器路径/channel、并发信号量、熔断）、登录（`interactive_login`、`import_cookie_header`、`has_login`、`login_status`）、各平台浏览器爬取 |
| `pipeline.py` | `RunContext`、`select_sources`、`run_sources`（守护线程 + 截止时间）、`process_results`、`build_report` |
| `trending.py` | 热榜抓取、RSS/Atom 解析、IDF 显著词跨平台合并、Markdown/JSON/HTML 渲染 |
| `schema.py` | 各平台条目 dataclass、`GlobalItem`、`Report`（`source_status`、通用 `from_dict`） |
| `normalize.py` / `score.py` / `dedupe.py` / `cluster.py` | 归一化、打分排序、去重、去掉主题词后的跨源关联与聚类 |
| `render.py` | 由注册表驱动的 compact / md / context / HTML 渲染；来源状态页脚 |
| `doctor.py` | `--diagnose`：每个平台实际会走的路径、登录态、浏览器健康、兜底引擎、海外源 |
| `env.py` | 配置加载（进程环境 > 项目 .env > 全局 .env）、运行开关导出、可用性探测 |
| `query.py` / `query_type.py` / `relevance.py` / `cjk.py` | 检索词（`search_keyword`、`overseas_query`）、查询类型、相关性、CJK 分词 |

---

## CLI（`scripts/last30days.py`）

```text
python3 scripts/last30days.py <topic> [--emit MODE] [--quick|--deep] [--days N] [--as-of DATE]
                              [--search SOURCES] [--global] [--global-query Q] [--no-browser]
                              [--refresh|--no-cache] [--cache-ttl H] [--save-dir DIR] [--timeout S] [--debug]
python3 scripts/last30days.py --hot [关键词] [--hot-sources IDS] [--hot-limit N] [--hot-title T] [--emit MODE]
python3 scripts/last30days.py login <weibo|xiaohongshu|zhihu|douyin|bilibili> [--cookie "..."] [--login-timeout S]
python3 scripts/last30days.py --diagnose [--probe-browser] [--emit json]
python3 scripts/last30days.py setup
python3 scripts/last30days.py --version
```

超时档位见 `pipeline.TIMEOUT_PROFILES`。启用 `upstream` 时，全局超时会自动延长。

---

## 输出

默认目录 `~/.local/share/last30days/out/`（可用 `LAST30DAYS_OUTPUT_DIR` 覆盖；无写权限时回退到系统临时目录）：

- 研究：`report.md`、`report.json`、`report.html`、`last30days.context.md`
- 热榜：`hot.md`、`hot.json`、`hot.html`

`report.json` 的 `source_status[<source>]` 包含 `state`（ok/empty/error/timeout）、`count`、`raw_count`、`elapsed`、`via`（数据路径计数），出错时还有 `error`。

缓存：`~/.cache/last30days-cn/`（`LAST30DAYS_CACHE_DIR`），默认 24 小时；只有至少一个平台有结果时才写缓存。

---

## 配置（摘要）

- 全局 `~/.config/last30days-cn/.env`，项目级 `.claude/last30days-cn.env`，目录可用 `LAST30DAYS_CN_CONFIG_DIR` 覆盖。
- 密钥类：`WEIBO_COOKIE`、`ZHIHU_COOKIE`、`BILIBILI_COOKIE`、`TIKHUB_API_KEY`/`DOUYIN_API_KEY`、`WECHAT_API_KEY`、`BAIDU_API_KEY`、`WEIBO_ACCESS_TOKEN`、`XIAOHONGSHU_API_BASE`、`GITHUB_TOKEN`（只读入配置，不写入进程环境）。
- 运行开关（写在 .env 中也会生效）：`LAST30DAYS_DEFAULT_SEARCH`、`INCLUDE_SOURCES`、`EXCLUDE_SOURCES`、`LAST30DAYS_DISABLE_BROWSER`、`LAST30DAYS_BROWSER_PATH`、`LAST30DAYS_BROWSER_CHANNEL`、`LAST30DAYS_BROWSER_CONCURRENCY`、`LAST30DAYS_WEBSEARCH_ENGINES`、`LAST30DAYS_USER_AGENT`、`LAST30DAYS_OUTPUT_DIR`、`LAST30DAYS_CACHE_DIR`、`LAST30DAYS_UPSTREAM`、`LAST30DAYS_UPSTREAM_PYTHON`、`LAST30DAYS_UPSTREAM_SEARCH`、`LAST30DAYS_HOT_SOURCES`、`LAST30DAYS_HOT_FEEDS`。
- 浏览器登录态保存在 `~/.config/last30days-cn/browser_cookies/`（`<平台>_cookies.json` 与 `<平台>_login.json`，权限 0600）。

完整键名以 `scripts/lib/env.py` 为准。
