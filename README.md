<p align="center">
  <img src="assets/banner.png" alt="last30days-cn — 中文互联网近 30 天研究引擎" width="900">
</p>

<p align="center">
  <b>简体中文</b> ·
  <a href="README.en.md">English</a>
</p>

# 📰 last30days-cn — 中文互联网近 30 天研究引擎

> 一个 AI Agent 技能（Skill）：搜索微博、小红书、B站、知乎、抖音、微信公众号、百度、今日头条 **最近 30 天真实用户在说什么**，按互动与时效排序、跨平台聚类，生成有据可查的研究报告；也能一键查看 **全网热榜**。

🔗 基于 [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill) 深度本土化，面向中文互联网平台。

当前版本：**`v4.0.0`** · 👤 作者：Jesse（[@Jesseovo](https://github.com/Jesseovo)）

```bash
npx skills add Jesseovo/last30days-skill-cn -g
```

---

## ✨ v4.0.0 有什么不同

v4 是一次大版本升级。所有平台接入都对照 2026 年 10 月的线上真实响应重新验证过，重点修复了「静默返回 0 条」和「把垃圾链接当证据」这两类老问题：

| 方面 | v3.2 | v4.0 |
|---|---|---|
| 一次默认研究耗时 | 常卡在各平台超时，数分钟 | 实测约 10 秒（无浏览器模式，8 平台并行，每个平台独立超时） |
| B站 | 不完整 UA 被 WAF 回 412（#17） | WBI 签名搜索 + buvid3 访客 Cookie + 完整 UA，并按发布时间限定在研究时间窗内 |
| 今日头条 | 旧接口恒为空，0 条 | 解析 `so.toutiao.com` 服务端渲染的结果卡片：真实标题、来源、日期、阅读/评论/点赞 |
| 微信公众号 | 把搜狗页面上的「图片/知乎/医疗」导航链接当成文章 | 只解析 `news-list` 结果卡片，带公众号名称与发布日期 |
| 百度 | 调用不存在的 API；网页结果拿不到真实链接和日期 | 改用官方千帆「AI 搜索」API；网页解析出真实链接、站点名、摘要、日期，跳过百度卡片与广告 |
| 小红书 / 微博 / 知乎 / 抖音 | 匿名请求被登录墙拦截，用户没有任何登录入口（#8 #11） | 新增 `login <平台>` 扫码保存登录态（或 `--cookie` 导入）；未登录时用热榜匹配 + 经过校验的公开搜索兜底，并说明原因与修复命令 |
| 兜底搜索 | 只有 Bing；部分地区被重定向回首页，或拿到无关的诱饵结果 | cn.bing → DuckDuckGo → www.bing 多引擎依次尝试，每条结果都要通过平台链接规则和主题相关性校验 |
| 诊断 | 所有路径都失败的平台仍显示 `true` | 逐平台说明实际会走哪条路径，并显示登录态、浏览器健康与兜底引擎状态 |
| 热点 | 无 | `--hot` 全网热榜，合并跨平台热点，可每天自动发布为 GitHub Pages 网站（#16） |
| 海外平台 | 无 | 可选启用 Hacker News / GitHub / Reddit，或桥接上游 last30days 获取 X/YouTube/TikTok（#9） |
| 旧电脑 | 只能手动配置浏览器路径 | 浏览器启动失败会自动切换到无浏览器模式；兼容 Python 3.8（Catalina 自带版本）（#13） |

### Issue 处理一览

| Issue | 结论 | 处理 |
|---|---|---|
| [#17](https://github.com/Jesseovo/last30days-skill-cn/issues/17) B站 WAF 对不完整 UA 回 412 | ✅ 已修复 | 所有平台统一使用完整浏览器 UA（可用 `LAST30DAYS_USER_AGENT` 覆盖）；B站改用 WBI 签名 + buvid3；412 时自动换会话并回退旧接口 |
| [#16](https://github.com/Jesseovo/last30days-skill-cn/issues/16) 想要一个只看每天热点的网站 | ✅ 已实现 | `--hot` 全网热榜 + `.github/workflows/daily-hot.yml`：一键启用后每天 3 次自动发布到 GitHub Pages；VC/互联网资讯可接入自定义 RSS（如 RSSHub） |
| [#13](https://github.com/Jesseovo/last30days-skill-cn/issues/13) 2012 MacBook Pro（Catalina）很多功能用不了 | ✅ 已改进 | 无浏览器模式成为一等公民；浏览器起不来时自动熔断；兼容 Python 3.8；`--diagnose --probe-browser` 可实测浏览器能否启动 |
| [#11](https://github.com/Jesseovo/last30days-skill-cn/issues/11) 小红书 XHR 改版只返回联想词 | ✅ 已修复 | 三重解析（XHR 笔记卡片 → `__INITIAL_STATE__` → DOM），新增登录入口；修正 xiaohongshu-mcp 接口（`POST /api/v1/feeds/search`）；笔记链接带 `xsec_token` |
| [#10](https://github.com/Jesseovo/last30days-skill-cn/issues/10) npx 安装 `File name too long` | ✅ v3.0 已修复 | 仓库中已无 symlink（有回归测试）；v4 新增 `.gitattributes` 固定 LF 换行 |
| [#9](https://github.com/Jesseovo/last30days-skill-cn/issues/9) 希望保留海外平台 | ✅ 可选开关 | 默认关闭；`--global` 启用免 Key 的 Hacker News / GitHub / Reddit；X/YouTube/TikTok 通过桥接本机已安装的上游 last30days 获取，不在中文版里重复维护几十个海外适配器 |
| [#8](https://github.com/Jesseovo/last30days-skill-cn/issues/8) 小红书 Playwright 拿不到数据 | ✅ 已改进 | 根因是缺少登录态：新增 `login xiaohongshu` 扫码登录；`--diagnose` 如实显示登录状态；评论里提到的知乎、抖音、头条一并处理（头条已恢复真实搜索） |

完整变更见 [release-notes.md](release-notes.md)。

---

## 🚀 快速开始

```bash
# 1. 安装（Claude Code / Codex / Cursor / Gemini CLI 等 Agent Skills 宿主）
npx skills add Jesseovo/last30days-skill-cn -g

# 2. 在 Agent 里直接说
#    「用 last30days 研究一下 AI 编程助手最近 30 天的讨论」
#    「今天全网有什么热点？」
```

也可以直接在命令行运行（Python 3.8+，**零硬依赖**）：

```bash
git clone https://github.com/Jesseovo/last30days-skill-cn.git && cd last30days-skill-cn
python scripts/last30days.py "AI编程助手"                  # 主题研究（8 平台并行）
python scripts/last30days.py "AI编程助手" --emit html-path # 生成可离线打开的 HTML 报告
python scripts/last30days.py --hot                         # 全网热榜
python scripts/last30days.py --diagnose                    # 看看哪些平台可用、怎么修
```

可选增强：

```bash
python -m pip install jieba                                      # 更好的中文分词（不装也能用）
python -m pip install playwright && python -m playwright install chromium   # 登录态平台需要
```

<details>
<summary>其他安装方式（手动 clone / Cursor / OpenClaw / Gemini CLI）</summary>

```bash
# Claude Code 手动安装
git clone https://github.com/Jesseovo/last30days-skill-cn.git ~/.claude/skills/last30days-cn
# OpenClaw / ClawHub
git clone https://github.com/Jesseovo/last30days-skill-cn.git ~/.agents/skills/last30days-cn
```

Cursor：将仓库克隆到本地后把 `SKILL.md` 添加为项目技能。Gemini CLI：克隆后作为扩展加载（见 `gemini-extension.json`）。任何支持 Bash / Read / Write 的 Agent 都可以使用。

</details>

---

## 🔥 全网热榜 & 每日热点网站（#16）

```bash
python scripts/last30days.py --hot                                  # 微博/百度/抖音/头条/B站/知乎 热榜（约 3 秒）
python scripts/last30days.py --hot AI                               # 只看与 AI 相关的热点
python scripts/last30days.py --hot --hot-sources boards,news,global # 加上科技资讯 RSS 与 Hacker News
python scripts/last30days.py --hot --emit html-path                 # 生成热榜网页
```

- **跨平台热点**：同一事件在不同平台的叫法往往不一样（「中国男足获亚运铜牌」/「拿下点球大战！U23国足获亚运铜牌」）。引擎会按显著词把它们合并，按「上了几个平台」排序；置顶等编辑性条目不参与合并。
- 热榜页面带关键词筛选、深色模式和手机布局，生成在 `~/.local/share/last30days/out/hot.html`。
- **自定义资讯源**：`LAST30DAYS_HOT_FEEDS="36氪快讯|https://你的RSSHub/36kr/newsflashes,X 列表|https://你的RSSHub/twitter/list/..."`。VC 融资、互联网公司新闻、Twitter 等可通过自建 RSSHub 接入。

### 一键发布成「只看每日热点」的网站

仓库自带 [`.github/workflows/daily-hot.yml`](.github/workflows/daily-hot.yml)，**默认不运行**。在你的仓库（或 fork）中：

1. Settings → Pages → Source 选择 **GitHub Actions**
2. Settings → Secrets and variables → Actions → **Variables** 新建 `HOT_PAGES` = `true`
3. （可选）`HOT_SOURCES`（默认 `boards,news,global`）、`HOT_FEEDS`（自定义 RSS）、`HOT_TITLE`（页面标题）
4. Actions → **Daily Hot Board** → Run workflow

之后每天北京时间 08:00 / 12:00 / 20:00 自动更新，地址为 `https://<你的用户名>.github.io/<仓库名>/`。Runner 在海外，个别平台（如知乎热榜）偶尔不可用，页面会如实标注。

---

## 🔐 登录态：小红书 / 微博 / 知乎 / 抖音

2025 年起，这几个平台的搜索对匿名访问基本都要求登录。v4 提供了正式的登录入口（需要 Playwright）：

```bash
python scripts/last30days.py login xiaohongshu   # 弹出浏览器，扫码登录一次即可
python scripts/last30days.py login weibo         # 也支持 zhihu / douyin / bilibili
```

- 登录态保存在 `~/.config/last30days-cn/browser_cookies/`（文件权限 600），之后的无头运行会自动复用；失效后会提示重新登录。
- **没有图形界面**（服务器 / SSH）时，可以把自己浏览器里复制的 Cookie 导入：
  `python scripts/last30days.py login zhihu --cookie "z_c0=...; _xsrf=..."`
- 也可以把 `WEIBO_COOKIE` / `ZHIHU_COOKIE` / `BILIBILI_COOKIE` 写进 `.env`。
- 未登录时不会静默失败：引擎会用热榜匹配 + 经过校验的公开搜索兜底，并在结果里标注「只有公开链接，缺少互动数据」。

---

## 🌏 海外平台（可选，#9）

```bash
python scripts/last30days.py "Claude Code 评测" --global                              # + Hacker News / GitHub / Reddit
python scripts/last30days.py "AI编程助手" --global --global-query "AI coding assistant" # 中文主题请给英文关键词
python scripts/last30days.py "Claude Code" --search x,youtube                           # 通过上游 last30days 桥接
```

- **免 Key**：Hacker News（Algolia）、GitHub（可配 `GITHUB_TOKEN` 提高额度）、Reddit（云服务器/代理 IP 常被 403，会明确提示）。
- **X / YouTube / TikTok / Instagram**：这些平台需要各自的 Key、Cookie 或 yt-dlp，上游项目已经在维护对应适配器。所以 v4 选择桥接：如果本机装了上游 skill（`npx skills add mvanhorn/last30days-skill -g`），中文版会以子进程方式调用它，把结果合并进同一份报告。上游需要 Python 3.12+，可用 `LAST30DAYS_UPSTREAM_PYTHON` 指定解释器。
- 默认关闭，不影响中文版开箱即用；也可在 `.env` 写 `INCLUDE_SOURCES=global` 常开。

---

## 💻 旧电脑 / 无浏览器模式（#13）

Playwright 自带的新版 Chromium 对系统版本要求越来越高（macOS Catalina 等旧系统常常启动不了）。v4 的做法：

- **无浏览器也能用**：B站、头条、微信、百度、各平台热榜都不需要浏览器；登录态平台会走热榜匹配 + 公开搜索兜底。
- **自动熔断**：浏览器启动失败一次，本次运行就不再尝试，并给出修复建议，不会每个平台各卡几十秒。
- **使用系统已有的浏览器**：

  ```bash
  export LAST30DAYS_BROWSER_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
  # 或 export LAST30DAYS_BROWSER_CHANNEL=chrome
  python scripts/last30days.py --diagnose --probe-browser   # 真实启动一次，验证能否使用
  ```

- **完全关闭浏览器**：加 `--no-browser`，或在 `.env` 写 `LAST30DAYS_DISABLE_BROWSER=1`。
- **兼容 Python 3.8**（Catalina 自带的 `/usr/bin/python3`），CI 中包含 3.8 测试。
- 机器较慢时可设置 `LAST30DAYS_BROWSER_CONCURRENCY=1`，同一时间只开一个浏览器。

---

## 📋 平台支持与数据路径

| 平台 | 主路径（按顺序尝试） | 无登录/无 Key 时 | 可选配置 |
|---|---|---|---|
| 🔴 微博 | 开放平台 API → 登录 Cookie 搜索 → 登录态浏览器 | 热搜榜匹配 + 公开搜索兜底 | `WEIBO_COOKIE` / `login weibo` / `WEIBO_ACCESS_TOKEN` |
| 📕 小红书 | xiaohongshu-mcp → 登录态浏览器（XHR/页面状态/DOM） | 公开搜索兜底（仅笔记链接） | `login xiaohongshu` / `XIAOHONGSHU_API_BASE` |
| 📺 B站 | WBI 签名搜索（时间窗内）→ 旧版接口 → 浏览器 | ✅ 完整可用 | `BILIBILI_COOKIE`（降低风控） |
| 💬 知乎 | Cookie 搜索 → 登录态浏览器 | 热榜匹配 + 公开搜索兜底 | `ZHIHU_COOKIE` / `login zhihu` |
| 🎵 抖音 | TikHub API → 登录态浏览器（页面自行签名） | 热榜匹配 + 公开搜索兜底 | `TIKHUB_API_KEY` / `login douyin` |
| 💚 微信公众号 | 极速数据 API → 搜狗微信 | ✅ 搜狗微信可用 | `WECHAT_API_KEY` |
| 🔵 百度 | 千帆 AI 搜索 API → 网页搜索 | 网页搜索（可能被安全验证拦截）+ 多引擎兜底 | `BAIDU_API_KEY` |
| 📰 今日头条 | so.toutiao.com 资讯搜索 + 热榜 | ✅ 完整可用 | — |
| 🌏 海外（可选） | Hacker News / GitHub / Reddit；上游桥接 X/YouTube/TikTok | — | `--global`、`GITHUB_TOKEN`、`LAST30DAYS_UPSTREAM` |

> 「公开搜索兜底」只能拿到公开链接，**没有可靠的互动数据和精确日期**。报告会明确标注，Agent 也会被要求不引用这类条目的互动数。

---

## ⚙️ 配置

所有配置都是可选的。运行 `python scripts/last30days.py setup` 会生成带注释的模板 `~/.config/last30days-cn/.env`（项目级配置为 `.claude/last30days-cn.env`）：

```ini
# 登录态（推荐用 login 命令扫码，无图形界面时再手动填写）
WEIBO_COOKIE=
ZHIHU_COOKIE=
BILIBILI_COOKIE=

# API Key
TIKHUB_API_KEY=          # 抖音
WECHAT_API_KEY=          # 微信公众号（极速数据）
BAIDU_API_KEY=           # 百度千帆「AI 搜索」（Bearer Key）
WEIBO_ACCESS_TOKEN=      # 微博开放平台
XIAOHONGSHU_API_BASE=    # 自部署 xiaohongshu-mcp，默认自动探测 127.0.0.1:18060
GITHUB_TOKEN=            # 海外 GitHub 源

# 运行开关（v4 起写在 .env 里也会生效）
LAST30DAYS_DISABLE_BROWSER=1
LAST30DAYS_BROWSER_PATH=
INCLUDE_SOURCES=global
EXCLUDE_SOURCES=douyin
LAST30DAYS_HOT_FEEDS=
```

Windows（PowerShell）创建配置目录：`New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.config\last30days-cn"`。

---

## 🧭 命令行参数

| 参数 | 说明 |
|---|---|
| `--emit` | `compact`（默认，给 Agent）/ `md` / `json` / `html` / `html-path` / `context` / `path` |
| `--quick` / `--deep` | 快速（按查询类型挑选平台）/ 深度（每个平台抓更多页） |
| `--days N` / `--as-of YYYY-MM-DD` | 回溯天数（1–30）/ 历史回溯的终点日期 |
| `--search SOURCES` | 平台、别名或分组：`weibo,xhs,bili,zhihu,douyin,wechat,baidu,toutiao`、`cn`、`global`、`all`、`hn`、`github`、`reddit`、`x`、`youtube`… |
| `--global` / `--global-query Q` | 启用海外源 / 海外源使用的英文关键词 |
| `--hot [关键词]` / `--hot-sources` / `--hot-limit` / `--hot-title` | 全网热榜相关 |
| `login <平台> [--cookie "..."]` | 保存平台登录态 |
| `--diagnose [--probe-browser] [--emit json]` | 诊断各平台路径 |
| `--no-browser` | 本次运行不使用浏览器 |
| `--refresh` / `--no-cache` / `--cache-ttl H` | 缓存控制（默认缓存 24 小时） |
| `--save-dir DIR` / `--timeout SECS` / `--debug` | 另存原始输出 / 全局超时 / 调试日志 |

输出文件位于 `~/.local/share/last30days/out/`：`report.md`、`report.json`、`report.html`、`last30days.context.md`，以及热榜的 `hot.md`、`hot.json`、`hot.html`（可用 `LAST30DAYS_OUTPUT_DIR` 覆盖）。

---

## 🩺 诊断示例

```text
last30days-cn 4.0.0-cn 数据源诊断
可用 3 / 降级 5 / 不可用 0

⚠️ 微博 (weibo): 微博搜索现需登录；当前只能用热搜榜匹配 + 公开搜索兜底
   命令: python scripts/last30days.py login weibo
⚠️ 小红书 (xiaohongshu): 未登录小红书：只能走公开搜索兜底（仅链接，无互动数据）
✅ B站 (bilibili): WBI 签名搜索可用
✅ 微信公众号 (wechat): 搜狗微信公开搜索可用
✅ 今日头条 (toutiao): 头条资讯搜索（so.toutiao.com）可用
...
浏览器（Playwright）  状态 / 外部浏览器 / 启动测试
登录态                小红书 / 微博 / 知乎 / 抖音 / B站
海外源                Hacker News / GitHub / Reddit / 上游桥接
```

---

## 📊 排序与聚类

每条结果的综合分（0–100）= **相关性 45% + 时效 25% + 互动 30%**，网页类来源（百度/公众号）只计相关性与时效。之后再做以下处理：

- **时间窗过滤**：带日期且不在研究时间窗内的结果会被剔除；无日期的结果保留，但会扣分并标注 `[日期:low]`。
- **去噪**：同平台近似重复去重；相关性过低的结果不保留；同一作者最多 3 条。
- **跨平台聚类**：比较前先去掉主题词本身（所有结果都含主题词，不能说明是同一事件），再判断是否为同一事件。

各平台互动指标：微博（转发/评论/点赞）、小红书（点赞/收藏/评论/分享）、B站（播放/弹幕/评论/点赞/收藏）、知乎（赞同/评论/收藏）、抖音（点赞/评论/分享/播放）、头条（阅读/评论/点赞）、海外（points/upvotes/★/评论）。

---

## 🏗️ 项目结构

```
last30days-skill-cn/
├── SKILL.md                    # Agent 技能说明（事实源）
├── scripts/                    # 运行时代码（事实源）
│   ├── last30days.py           # CLI 入口：研究 / --hot / login / --diagnose / setup
│   └── lib/
│       ├── sources.py          # 数据源注册表（标签、前缀、分组、别名）
│       ├── pipeline.py         # 并行检索 → 归一化 → 打分 → 去重 → 聚类
│       ├── http.py             # 浏览器级请求头、gzip/GBK、Cookie 会话、412 快速失败
│       ├── websearch.py        # 多引擎公开搜索兜底 + 结果校验
│       ├── crawler_bridge.py   # Playwright：登录、熔断、并发限制、XHR/页面状态解析
│       ├── weibo.py xiaohongshu.py bilibili.py zhihu.py douyin.py wechat.py baidu.py toutiao.py
│       ├── hackernews.py github.py reddit.py upstream_bridge.py   # 可选海外源
│       ├── trending.py         # 全网热榜
│       ├── render.py           # compact / md / json / Swiss-IKB HTML
│       └── doctor.py env.py schema.py score.py dedupe.py cluster.py ...
├── skills/last30days/          # 生成的可安装载荷（python scripts/build_payload.py）
├── tests/                      # 357 个回归测试（无网络）
└── .github/workflows/          # CI（含 Python 3.8 / macOS）与每日热榜发布
```

开发说明见 [CLAUDE.md](CLAUDE.md)，技术规格见 [SPEC.md](SPEC.md)。

---

## ⚠️ 免责声明 / Disclaimer

> **请务必仔细阅读以下内容。使用本项目即表示您同意以下所有条款。**

### 法律合规声明

1. **本项目仅供学习和研究目的**。所有爬虫功能仅用于技术学习与研究交流，**严禁用于商业用途**。
2. 使用者必须严格遵守中华人民共和国相关法律法规，包括但不限于：
   - 《中华人民共和国网络安全法》
   - 《中华人民共和国数据安全法》
   - 《中华人民共和国个人信息保护法》
   - 《中华人民共和国反不正当竞争法》
3. 使用者必须遵守各平台的**服务条款（ToS）**和 **robots.txt** 规定。
4. **禁止**将本项目用于以下行为：
   - 大规模、高频率地抓取平台数据
   - 收集、存储或传播他人个人隐私信息
   - 破坏或干扰平台正常运营
   - 任何形式的非法数据倒卖或商业牟利
   - 对外提供自动化数据采集服务
5. 本项目开发者**不承担**因使用本项目而产生的任何法律责任。用户应**自行承担**使用本项目的全部法律风险。
6. 如有侵权，请联系作者，将在第一时间处理。

### 技术免责

- 浏览器模式依赖 Playwright 驱动真实浏览器，复用用户本人登录的会话，由页面自己发出请求，**不涉及**逆向加密算法或破解安全机制。
- 各平台接口随时可能变更，本项目不保证所有功能始终可用。
- 建议将请求频率控制在合理范围内（如每次搜索间隔 ≥ 5 秒），避免被平台封禁。

> 💡 **爬虫违法违规的案例频发，请务必合法合规使用。**
> 参考：[中国爬虫相关法律案例汇总](https://github.com/HiddenStrawberry/Crawler_Illegal_Cases_In_China)

---

## 🙏 致谢

- [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill) — 原始英文版项目（v4 的海外平台桥接即调用它）
- [NanmiCoder/MediaCrawler](https://github.com/NanmiCoder/MediaCrawler) — 浏览器复用登录态的思路来源
- [xpzouying/xiaohongshu-mcp](https://github.com/xpzouying/xiaohongshu-mcp) — 可选的小红书数据服务
- [op7418/guizang-ppt-skill](https://github.com/op7418/guizang-ppt-skill) — HTML 报告的 Swiss/IKB 视觉语言

## 📜 许可证

[MIT License](LICENSE) · 原始项目 [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill) by Matt Van Horn · 中文本土化 Jesse（[@Jesseovo](https://github.com/Jesseovo)）
