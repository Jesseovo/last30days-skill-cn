# Release Notes

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
