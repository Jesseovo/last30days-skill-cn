<p align="center">
  <img src="assets/banner.png" alt="last30days-cn — 中文互联网近 30 天研究引擎" width="900">
</p>

<p align="center">
  <b>简体中文</b> ·
  <a href="README.en.md">English</a>
</p>

# last30days-cn

**中文互联网近 30 天研究引擎。** 让 AI Agent 去微博、小红书、B站、知乎、抖音、微信公众号、百度、今日头条看看最近大家到底在说什么，按互动和时效排序、跨平台归并，写成每条结论都有出处的研究报告。也可以一条命令查看全网热榜。

```bash
npx skills add Jesseovo/last30days-skill-cn -g
```

装好后直接对你的 Agent 说：

> 用 last30days 研究一下「新能源汽车价格战」最近 30 天的讨论
>
> 今天全网有什么热点？

---

## 它能做什么

- **主题研究**：8 个平台并行检索，按相关性、时效、互动打分；同一事件在多个平台出现时归并为「跨平台热点」。输出有四种：给 Agent 的精简证据、完整 Markdown、JSON、可离线打开的 HTML 报告。
- **全网热榜**：不需要主题，汇总微博、百度、抖音、头条、B站、知乎热榜并合并跨平台热点；可加入科技资讯 RSS 和 Hacker News，还能每天自动发布成热点网页。
- **如实交代覆盖情况**：报告末尾逐平台列出拿到多少条、走了哪条数据路径；失败的平台写明原因和修复命令，不会把「没拿到数据」说成「没人讨论」。
- **登录态复用**：需要登录的平台扫码一次即可长期使用；没有图形界面时可以导入 Cookie。
- **海外视角（可选）**：Hacker News、GitHub、Reddit，以及通过上游 [last30days](https://github.com/mvanhorn/last30days-skill) 获取 X、YouTube、TikTok。
- **轻量**：只依赖 Python 3.8+ 标准库，浏览器和分词都是可选增强，旧电脑也能用。

---

## 快速开始

**作为 Agent 技能使用**（Claude Code、Codex、Cursor、Gemini CLI 等支持 Agent Skills 的工具）：

```bash
npx skills add Jesseovo/last30days-skill-cn -g
```

**直接在命令行使用：**

```bash
git clone https://github.com/Jesseovo/last30days-skill-cn.git
cd last30days-skill-cn
python scripts/last30days.py "AI编程助手"      # 研究一个主题
python scripts/last30days.py --hot              # 全网热榜
python scripts/last30days.py --diagnose         # 查看各平台是否可用、怎么修
```

**可选增强：**

```bash
python -m pip install jieba                                                  # 更准的中文分词
python -m pip install playwright && python -m playwright install chromium    # 登录态平台需要
```

<details>
<summary>其他安装方式</summary>

```bash
# Claude Code 手动安装
git clone https://github.com/Jesseovo/last30days-skill-cn.git ~/.claude/skills/last30days-cn
# OpenClaw / ClawHub
git clone https://github.com/Jesseovo/last30days-skill-cn.git ~/.agents/skills/last30days-cn
```

- Cursor：克隆仓库后，把 `SKILL.md` 添加为项目技能。
- Gemini CLI：克隆后作为扩展加载（见 `gemini-extension.json`）。
- 其他 Agent：只要支持 Bash、Read、Write 就能用。

</details>

---

## 使用

### 研究一个主题

```bash
python scripts/last30days.py "AI编程助手"                       # 默认：8 个平台、最近 30 天
python scripts/last30days.py "AI编程助手" --emit html-path      # 生成 HTML 报告并输出路径
python scripts/last30days.py "AI编程助手" --deep                # 每个平台抓更多
python scripts/last30days.py "AI编程助手" --quick               # 只跑和问题类型最相关的平台
python scripts/last30days.py "AI编程助手" --search bili,zhihu,xhs
python scripts/last30days.py "AI编程助手" --days 7
python scripts/last30days.py "AI编程助手" --as-of 2026-05-01    # 回看某个历史时间窗
```

输出示例（格式示意）：

```text
🌐 last30days-cn v4.0.0-cn · 数据截至 2026-10-03
## 研究结果: AI编程助手

### 🔗 跨平台聚合热点
- **某工具发布新版本** — 覆盖 B站、今日头条、微博（4 条）

### B站视频
**BL1** (得分:95) 某UP主 (2026-09-28) [1,446播放, 140收藏, 116点赞]
  2026 最新 Codex 完整教程
  https://www.bilibili.com/video/BV...

---
**来源:**
  ✅ B站: 18 条（路径: wbi-search×20）
  ✅ 今日头条: 6 条（原始 15 条，按时间窗/相关性保留）（路径: so.toutiao×15）
  ❌ 小红书: 小红书搜索需要登录态：运行 `python scripts/last30days.py login xiaohongshu` …
```

报告文件保存在 `~/.local/share/last30days/out/`：`report.md`、`report.json`、`report.html`、`last30days.context.md`。

### 全网热榜

```bash
python scripts/last30days.py --hot                                   # 微博 / 百度 / 抖音 / 头条 / B站 / 知乎
python scripts/last30days.py --hot AI                                # 只看和某个主题有关的热点
python scripts/last30days.py --hot --hot-sources boards,news,global  # 加上科技资讯 RSS 与 Hacker News
python scripts/last30days.py --hot --emit html-path                  # 生成热榜网页
```

- 同一件事在不同平台的叫法往往不同（「中国男足获亚运铜牌」/「拿下点球大战！U23国足获亚运铜牌」），热榜会按关键词把它们合并成一条「跨平台热点」，按登上的平台数排序。
- 热榜网页带关键词筛选、深色模式和手机布局。
- 自定义资讯源：设置 `LAST30DAYS_HOT_FEEDS="名称|RSS地址,名称|RSS地址"`，例如自建 [RSSHub](https://docs.rsshub.app/) 的 36 氪快讯或 X 列表。

### 每日热点网站

仓库自带 GitHub Actions 工作流 [`.github/workflows/daily-hot.yml`](.github/workflows/daily-hot.yml)，可以把热榜每天自动发布成一个网页。**默认不运行**，在你的仓库（或 fork）中启用：

1. Settings → Pages → Source 选择 **GitHub Actions**
2. Settings → Secrets and variables → Actions → Variables，新建 `HOT_PAGES`，值为 `true`
3. （可选）设置变量 `HOT_SOURCES`（默认 `boards,news,global`）、`HOT_FEEDS`（自定义 RSS）、`HOT_TITLE`（页面标题）
4. Actions → **Daily Hot Board** → Run workflow

之后每天北京时间 08:00、12:00、20:00 自动更新，地址为 `https://<用户名>.github.io/<仓库名>/`。

### 需要登录的平台

小红书、微博、知乎、抖音的搜索基本都要求登录。扫码登录一次即可（需要 Playwright）：

```bash
python scripts/last30days.py login xiaohongshu   # 也支持 weibo / zhihu / douyin / bilibili
```

- 登录态保存在 `~/.config/last30days-cn/browser_cookies/`（仅当前用户可读），之后的检索会自动复用；过期后会提示重新登录。
- 服务器、SSH 等没有图形界面的环境，可以导入自己浏览器里复制的 Cookie：

  ```bash
  python scripts/last30days.py login zhihu --cookie "z_c0=...; _xsrf=..."
  ```

- 也可以在配置文件里填 `WEIBO_COOKIE`、`ZHIHU_COOKIE`、`BILIBILI_COOKIE`。
- 不登录也能用：这些平台会改用热榜匹配和公开搜索兜底，报告里会注明「只有公开链接，缺少互动数据」。

### 海外平台（可选）

```bash
python scripts/last30days.py "Claude Code 评测" --global                                # 加上 Hacker News / GitHub / Reddit
python scripts/last30days.py "AI编程助手" --global --global-query "AI coding assistant"  # 中文主题需提供英文关键词
python scripts/last30days.py "Claude Code" --search x,youtube                            # 通过上游 last30days 获取
```

- Hacker News、GitHub、Reddit 不需要 Key。GitHub 可配置 `GITHUB_TOKEN` 提高额度；Reddit 会拒绝部分云服务器 IP，遇到时会明确提示。
- X、YouTube、TikTok、Instagram 通过本机安装的上游 skill 获取（`npx skills add mvanhorn/last30days-skill -g`，需要 Python 3.12+）。
- 默认关闭；想长期开启可以在配置里写 `INCLUDE_SOURCES=global`。

### 旧电脑与无浏览器模式

- B站、头条、微信公众号、百度和全网热榜都不需要浏览器。
- 浏览器启动失败时，本次运行会自动切换到无浏览器模式，并提示修复方法，不会让每个平台各卡一遍。
- 新版 Chromium 在旧系统（如 macOS Catalina）上启动不了时，可以改用系统已经装好的浏览器：

  ```bash
  export LAST30DAYS_BROWSER_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
  python scripts/last30days.py --diagnose --probe-browser    # 真实启动一次，确认可用
  ```

- 完全不用浏览器：加 `--no-browser`，或在配置里写 `LAST30DAYS_DISABLE_BROWSER=1`。
- 机器性能一般时，设置 `LAST30DAYS_BROWSER_CONCURRENCY=1` 让浏览器一个一个开。
- 支持 Python 3.8（macOS Catalina 自带的 `python3`）。

---

## 平台与数据路径

| 平台 | 数据路径（按顺序尝试） | 不登录 / 不配置时 | 可选配置 |
|---|---|---|---|
| 🔴 微博 | 开放平台 API → 登录 Cookie 搜索 → 登录态浏览器 | 热搜榜匹配 + 公开搜索 | `login weibo`、`WEIBO_COOKIE`、`WEIBO_ACCESS_TOKEN` |
| 📕 小红书 | xiaohongshu-mcp → 登录态浏览器 | 公开搜索（仅笔记链接） | `login xiaohongshu`、`XIAOHONGSHU_API_BASE` |
| 📺 B站 | WBI 签名搜索 → 备用接口 → 浏览器 | ✅ 完整可用 | `BILIBILI_COOKIE` |
| 💬 知乎 | Cookie 搜索 → 登录态浏览器 | 热榜匹配 + 公开搜索 | `login zhihu`、`ZHIHU_COOKIE` |
| 🎵 抖音 | TikHub API → 登录态浏览器 | 热榜匹配 + 公开搜索 | `login douyin`、`TIKHUB_API_KEY` |
| 💚 微信公众号 | 极速数据 API → 搜狗微信 | ✅ 搜狗微信可用 | `WECHAT_API_KEY` |
| 🔵 百度 | 千帆 AI 搜索 API → 网页搜索 | 网页搜索 + 公开搜索 | `BAIDU_API_KEY` |
| 📰 今日头条 | 资讯搜索 + 热榜 | ✅ 完整可用 | — |
| 🌏 海外（可选） | Hacker News / GitHub / Reddit；上游桥接 X / YouTube / TikTok | — | `--global`、`GITHUB_TOKEN` |

「公开搜索」指通过搜索引擎查找该平台的公开页面，只能拿到链接和摘要，**没有可靠的互动数据和精确日期**。报告会把这类结果单独标出。

---

## 配置

所有配置都是可选的。运行 `python scripts/last30days.py setup` 会生成带注释的配置模板 `~/.config/last30days-cn/.env`（项目级配置放在 `.claude/last30days-cn.env`）：

```ini
# 登录态（推荐用 login 命令扫码；没有图形界面时再手动填写）
WEIBO_COOKIE=
ZHIHU_COOKIE=
BILIBILI_COOKIE=

# API Key
TIKHUB_API_KEY=          # 抖音
WECHAT_API_KEY=          # 微信公众号（极速数据）
BAIDU_API_KEY=           # 百度千帆「AI 搜索」
WEIBO_ACCESS_TOKEN=      # 微博开放平台
XIAOHONGSHU_API_BASE=    # 自部署的 xiaohongshu-mcp，默认自动探测 127.0.0.1:18060
GITHUB_TOKEN=            # 海外 GitHub 源

# 运行开关
LAST30DAYS_DISABLE_BROWSER=1     # 不使用浏览器
LAST30DAYS_BROWSER_PATH=         # 指定本机浏览器
INCLUDE_SOURCES=global           # 默认附带海外源
EXCLUDE_SOURCES=douyin           # 默认排除某些平台
LAST30DAYS_HOT_FEEDS=            # 热榜自定义 RSS
```

优先级：命令行环境变量 > 项目级配置 > 全局配置。Windows（PowerShell）创建配置目录：`New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.config\last30days-cn"`。

---

## 命令参考

| 参数 | 说明 |
|---|---|
| `--emit` | `compact`（默认，给 Agent 用）/ `md` / `json` / `html` / `html-path` / `context` / `path` |
| `--quick` / `--deep` | 快速（只跑与问题类型最相关的平台）/ 深度（每个平台抓更多） |
| `--days N` | 回溯天数，1–30，默认 30 |
| `--as-of YYYY-MM-DD` | 以指定日期为终点回溯 |
| `--search SOURCES` | 平台或分组：`weibo`、`xhs`、`bili`、`zhihu`、`douyin`、`wechat`、`baidu`、`toutiao`、`cn`、`global`、`all`、`hn`、`github`、`reddit`、`x`、`youtube` 等 |
| `--global` / `--global-query Q` | 启用海外源 / 海外源使用的英文关键词 |
| `--hot [关键词]` | 全网热榜；配合 `--hot-sources`、`--hot-limit`、`--hot-title` |
| `login <平台> [--cookie "..."]` | 保存平台登录态 |
| `--diagnose [--probe-browser]` | 诊断各平台；`--emit json` 输出机器可读结果 |
| `setup` | 首次配置，生成配置模板 |
| `--no-browser` | 本次运行不使用浏览器 |
| `--refresh` / `--no-cache` / `--cache-ttl H` | 缓存控制（默认缓存 24 小时） |
| `--save-dir DIR` / `--timeout SECS` / `--debug` | 另存输出 / 全局超时 / 调试日志 |

---

## 工作原理

1. **检索**：各平台并行运行，每个平台有自己的超时，一个平台卡住不影响其他平台。每个平台按「API → 登录态 → 公开接口 → 公开搜索」逐级尝试。
2. **清洗**：统一字段 → 过滤研究时间窗外的内容 → 同平台去重 → 去掉与主题无关的结果 → 同一作者最多保留 3 条。
3. **打分**：综合分（0–100）= 相关性 45% + 时效 25% + 互动 30%。网页类来源（百度、公众号）只看相关性和时效。
4. **归并**：比较不同平台的内容时先去掉主题词本身，再判断是否在说同一件事，避免仅因提到同一主题就被误判为同一事件。
5. **输出**：精简证据给 Agent 归纳，同时写出完整报告文件。

各平台的互动指标：微博（转发 / 评论 / 点赞）、小红书（点赞 / 收藏 / 评论 / 分享）、B站（播放 / 弹幕 / 评论 / 点赞 / 收藏）、知乎（赞同 / 评论 / 收藏）、抖音（点赞 / 评论 / 分享 / 播放）、头条（阅读 / 评论 / 点赞）。

---

## 项目结构

```
last30days-skill-cn/
├── SKILL.md                 # Agent 读取的技能说明
├── scripts/
│   ├── last30days.py        # 命令行入口
│   └── lib/                 # 平台适配、检索流水线、热榜、渲染、诊断等
├── skills/last30days/       # 自动生成的可安装技能包（勿手动修改）
├── tests/                   # 回归测试（不联网）
└── .github/workflows/       # CI 与每日热榜发布
```

参与开发请先阅读 [AGENTS.md](AGENTS.md)，技术细节见 [SPEC.md](SPEC.md)，版本变化见 [release-notes.md](release-notes.md)。

---

## ⚠️ 免责声明

> **请务必仔细阅读以下内容。使用本项目即表示您同意以下所有条款。**

1. **本项目仅供学习和研究目的**，严禁用于商业用途。
2. 使用者必须遵守中华人民共和国相关法律法规，包括但不限于《网络安全法》《数据安全法》《个人信息保护法》《反不正当竞争法》。
3. 使用者必须遵守各平台的**服务条款**和 **robots.txt** 规定。
4. **禁止**将本项目用于以下行为：
   - 大规模、高频率抓取平台数据
   - 收集、存储或传播他人个人信息
   - 破坏或干扰平台正常运营
   - 数据倒卖或任何商业牟利
   - 对外提供自动化数据采集服务
5. 本项目开发者**不承担**因使用本项目而产生的任何法律责任，使用者**自行承担**全部法律风险。
6. 如有侵权，请联系作者，将第一时间处理。

浏览器模式驱动真实浏览器、复用**你本人**登录的会话，由页面自己发出请求，不涉及逆向加密算法或破解安全机制。各平台接口随时可能变更，本项目不保证所有功能始终可用。请控制请求频率（建议每次搜索间隔 ≥ 5 秒）。

> 💡 爬虫违法违规的案例频发，请务必合法合规使用。参考：[中国爬虫相关法律案例汇总](https://github.com/HiddenStrawberry/Crawler_Illegal_Cases_In_China)

---

## 致谢

- [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill)：原版项目，也是海外平台桥接的对象
- [NanmiCoder/MediaCrawler](https://github.com/NanmiCoder/MediaCrawler)：复用浏览器登录态的思路来源
- [xpzouying/xiaohongshu-mcp](https://github.com/xpzouying/xiaohongshu-mcp)：可选的小红书数据服务
- [op7418/guizang-ppt-skill](https://github.com/op7418/guizang-ppt-skill)：HTML 报告的视觉风格来源

## 许可证

[MIT License](LICENSE)。原始项目 [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill)（Matt Van Horn），中文本土化 Jesse（[@Jesseovo](https://github.com/Jesseovo)）。
