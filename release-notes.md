# Release Notes

## v4.0.0（2026-10）

v4 是一次大版本升级。所有平台接入都对照 2026 年 10 月的线上真实响应重新验证过，目标是：**不再静默返回 0 条，不再把无关链接当证据，每个失败都说明原因和修复方式。**

### 亮点

- **全网热榜**（#16）：`--hot` 并行抓取微博/百度/抖音/头条/B站/知乎热榜（约 3 秒），按显著词合并「跨平台热点」，并支持关键词过滤、科技资讯 RSS、自定义 RSS 和 Hacker News。新增可选的 GitHub Pages 每日发布工作流（默认关闭）。
- **登录入口**（#8 #11）：`login <平台>` 扫码保存登录态，或用 `--cookie` 导入浏览器 Cookie；`--diagnose` 显示各平台登录状态。
- **海外源**（#9）：默认关闭；`--global` 启用免 Key 的 Hacker News / GitHub / Reddit；`--search x,youtube,...` 桥接本机已安装的上游 last30days。
- **旧电脑**（#13）：浏览器启动失败自动熔断并切换到无浏览器模式；支持 Python 3.8；`--no-browser`；`--diagnose --probe-browser`。
- **更快、更诚实**：8 平台并行，每个平台独立超时（实测默认研究约 10 秒）；报告页脚列出各平台状态、实际数据路径、原始条数与保留条数。

### 平台修复

- **B站**（#17）：完整浏览器 UA + WBI 签名搜索 + buvid3/buvid4 访客 Cookie；用 `pubtime_begin_s/end_s` 把结果限定在研究时间窗内；遇到 412/-412/-352 时换新会话并回退旧接口；可选 `BILIBILI_COOKIE`。
- **小红书**：修正 xiaohongshu-mcp 调用（`POST /api/v1/feeds/search`，旧版 GET 作兼容回退）；笔记链接带 `xsec_token`；浏览器模式三重解析（XHR 卡片 → `__INITIAL_STATE__` → DOM）；移除恒为 404 的 `fe_api` 接口。
- **微博**：识别匿名搜索返回的 `ok=-100` 登录墙；支持 `WEIBO_COOKIE` 与浏览器登录态；匹配热搜榜；公开搜索兜底；无法搜索时给出修复命令。
- **知乎**：仅在配置 Cookie 时调用 search_v3（匿名必然 400/403）；浏览器模式改为拦截页面自己的 search_v3 请求；热榜匹配。
- **抖音**：移除恒为空的无签名接口；新增热榜匹配；浏览器模式拦截搜索请求并带上发布日期；TikHub 接口沿用。
- **今日头条**：旧 `/api/search/content/` 已失效，改为解析 `so.toutiao.com` 服务端渲染的结果卡片（标题、来源、日期、阅读/评论/点赞）；偶发的空页面壳会自动重试。
- **微信公众号**：修复把搜狗页面导航链接（「图片」「知乎」「医疗」）当成文章、日期错位的问题，只解析 `news-list` 结果卡片。
- **百度**：`api.baidu.com/search/v1` 不是公开 API，改为官方千帆「AI 搜索」`web_search`（`BAIDU_API_KEY`，Bearer）；网页解析适配 2025+ 新版页面（`mu` 真实链接、站点名、摘要、日期），跳过百度卡片与广告。

### 引擎

- 新增 `lib/sources.py` 数据源注册表与 `lib/pipeline.py` 流水线，替代 8 段复制粘贴的编排代码；`--search` 支持别名与分组（`cn` / `global` / `all`）。
- 新增 `lib/http.py` 统一请求层：完整 UA、client hints、gzip/GBK 解码、Cookie 会话、412 快速失败；`--debug` 现在真正生效。
- 新增 `lib/websearch.py` 多引擎兜底（cn.bing → DuckDuckGo → www.bing）：解析跳转链接，按引擎节流，记住本次运行中已被拦截的引擎，并校验平台链接格式与主题相关性。
- 平台检索词保留用户原始写法（「AI编程助手」不再变成「ai 编程 助手」）。
- 跨平台关联与聚类先去掉主题词再比较，避免只因都提到主题就被聚成「同一事件」。
- 相关性过滤不再保留纯噪声（相关性 < 0.1）。
- 修复 v3 渲染错误：小红书「收藏」实为分享数、知乎赞同数不显示、公众号名称不显示、头条来源/摘要丢失。
- HTML 报告支持深色模式，并显示各平台的错误说明。

### 配置

- `.env` 中的运行开关（`LAST30DAYS_DISABLE_BROWSER`、`EXCLUDE_SOURCES`、`INCLUDE_SOURCES` 等）现在生效；v3 只读取进程环境变量。
- 新增可选键：`WEIBO_COOKIE`、`BILIBILI_COOKIE`、`GITHUB_TOKEN`；`setup` 会生成带注释的 `.env` 模板。
- xiaohongshu-mcp 仅在配置了 `XIAOHONGSHU_API_BASE`，或本机 `127.0.0.1:18060` 有响应时使用。

### 不兼容变更

- 不带 `--search` 时默认运行全部 8 个中文平台（与文档一致；v3 会按查询类型悄悄去掉部分平台）。`--quick` 仍按查询类型分层。
- `report.json` 新增 `search_topic`、`query_type`、`depth`、`source_status`，以及启用海外源时的 `hackernews` / `github` / `reddit` / `upstream` 列表。
- `BAIDU_API_KEY` 现在是千帆 AI 搜索的 Bearer Key，`BAIDU_SECRET_KEY` 不再需要。
- 缓存键加入 `v4` 前缀，v3 的缓存不会被复用。

### Issue 处理

| Issue | 结论 |
|---|---|
| #17 B站 412 | 已修复（完整 UA + WBI + buvid3 + 412 回退） |
| #16 每日热点网站 | 已实现（`--hot` + GitHub Pages 工作流） |
| #13 旧电脑 | 已改进（自动熔断、Python 3.8、`--no-browser`、浏览器实测） |
| #11 小红书 XHR 改版 | 已修复（三重解析 + 登录入口 + MCP 接口修正） |
| #10 npx 安装失败 | v3.0 已修复，v4 新增 `.gitattributes` |
| #9 海外平台 | 可选开关（原生 HN/GitHub/Reddit + 上游桥接） |
| #8 小红书 Playwright 无数据 | 已改进（根因为缺少登录态；知乎/抖音/头条一并处理） |

### 验证

- `python -m pytest tests -q`：357 个测试（其中 140 个为新增，测试中不访问网络），Windows 下 356 passed / 1 skipped（POSIX 权限测试）。
- 每个提交都在独立 worktree 中跑过测试与载荷一致性检查。
- 2026-10-03 实测（日本网络、无浏览器、无登录）：
  - 主题研究约 10 秒，B站 / 头条 / 微信 / 百度 / 知乎（兜底）有结果。
  - 微博 / 小红书 / 抖音按预期给出登录提示。
  - `--hot` 12 个来源全部成功，用时约 3 秒。
  - Hacker News / GitHub 正常，Reddit 403 时提示明确。
  - 上游桥接对接本地 mvanhorn/last30days 成功。

### 升级提示

- 用小红书、微博、知乎、抖音前，先运行一次 `python scripts/last30days.py login <平台>`（需要 Playwright）。
- 想要每日热点网站：按 README 设置 `HOT_PAGES=true` 并开启 GitHub Pages。

## v3.2.0

- 修复小红书新版搜索页将 `search/recommend` 联想词与笔记搜索混淆的问题，按笔记卡片 payload 动态识别结果并主动提交搜索框。
- 增加 `LAST30DAYS_BROWSER_PATH`、`LAST30DAYS_BROWSER_CHANNEL` 和 `LAST30DAYS_DISABLE_BROWSER`，支持旧 macOS 使用兼容的系统浏览器或完全走公开搜索兜底。
- `--diagnose` 增加浏览器模式与路径信息，版本统一到 `3.2.0` / `3.2.0-cn`。

## v3.1.0

面向可靠性、可维护性和 Agent Skills 发布流程的优化版本。

- 日期解析全面按北京时间（CST）归档，修复非北京时间环境下的跨日边界偏移。
- HTTP 请求统一指数退避、抖动、封顶和 Retry-After 解析，并对 debug URL 中的 key/token/secret 脱敏。
- 新增可选 `jieba` 的 CJK 分词模块；未安装时自动使用字符 bigram 回退，保持零硬依赖运行。
- 根目录 `SKILL.md` + `scripts/` 成为唯一事实源，新增 `scripts/build_payload.py --check` 防止 payload 漂移。
- 版本统一到 `3.1.0` / `3.1.0-cn`，并新增版本一致性测试。
- 缓存正式接线，支持 `--no-cache`、`--refresh`、`--cache-ttl`。
- 新增 GitHub Actions CI，覆盖 Windows/Linux、Python 3.9/3.12、无依赖/jieba 两种环境。

## v3.0.0

中文分支 v3 维护升级。

### 重点更新

- 新增 `skills/last30days` 自包含 Agent Skills 运行载荷。
- 中文 CLI 统一使用单入口 `last30days.py`，根目录和 Skill 载荷保持同名结构。
- 新增 `--emit html` 和 `--emit html-path`，支持生成可离线打开的 `report.html`。
- 引入受 `op7418/guizang-ppt-skill` 启发的 Swiss/IKB HTML 报告样式。
- README、Skill 说明、SPEC 与同步脚本统一改为推荐 `last30days.py`。
- README 在原先长文档基础上合入 v3 内容，保留免责声明、平台支持、配置、评分系统和中英文说明。

### 修复与改进

- 小红书和知乎在 API 与 Playwright 路径返回空结果时，增加公开站内搜索兜底。
- `quick` 模式下小红书和知乎跳过较慢的 Playwright 路径，避免长时间等待后超时。
- 小红书和知乎空结果时会明确说明已尝试路径和可能原因。
- `--diagnose` 在可尝试兜底路径时会把小红书标记为可用。
- 增加小红书/知乎兜底解析与可用性诊断回归测试。
- 增加 HTML 渲染回归测试。

### 兼容性

根目录 `scripts/` 仍保留用于本地开发和旧用法。通过 Agent Skills 安装时，推荐使用 `{{SKILL_DIR}}/scripts/last30days.py`。

### 已知限制

小红书和知乎仍可能因登录态失效、验证码/反爬、平台 API 变化、搜索引擎未收录公开链接而返回 0 条。当前版本会明确暴露原因，不再静默失败。

### 验证

```bash
py -m pytest tests/test_html_render.py tests/test_render_wechat.py
```

## v2.1.0

- 修复微信公众号渲染回归。
- 改进百度与小红书兜底行为。
- 增加爬虫和反爬相关回归覆盖。

## v2.0.0

- 增加受 MediaCrawler 启发的 Playwright 兜底路径。
- 降低强制 API Key 依赖。
- 增加多 Agent 兼容文档。

## v1.0.0

- 首次完成 `mvanhorn/last30days-skill` 的中文平台本土化。
