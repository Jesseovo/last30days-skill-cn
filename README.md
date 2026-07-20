<p align="center">
  <img src="assets/banner.png" alt="last30days-cn — 中国平台深度研究引擎" width="900">
</p>

<p align="center">
  <b>简体中文</b> ·
  <a href="README.en.md">English</a>
</p>

# 📰 last30days-cn — 中国平台深度研究引擎

> 🚀 30 天的研究，30 秒的结果。8 大平台。零过时信息。

**last30days-cn** 是一个 AI Agent 技能（Skill），能够自动搜索中国互联网 8 大主流平台最近 30 天的内容，综合分析后生成有据可查的研究报告。

🔗 本项目基于 [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill) 进行深度本土化改造，完全面向中国用户和中文互联网平台。

🕷️ v2.0 集成 [MediaCrawler](https://github.com/NanmiCoder/MediaCrawler) 爬虫引擎思路，大幅减少 API Key 依赖。v2.1 修复百度/小红书反爬问题，XHR 拦截替代 DOM 解析，Bing 兜底搜索，已移除无效的 ScrapeCreators 小红书集成。

当前版本：`v3.2.0`

👤 **作者 / Author:** Jesse ([@Jesseovo](https://github.com/Jesseovo))

---

## ✨ v3.2.0 优化内容

- 修复小红书新版搜索页只触发 `search/recommend` 联想词的问题：不再把 `sug_items` 当成笔记，而是按响应中的笔记卡片识别结果，并在必要时主动提交搜索框。
- Playwright 爬虫不再依赖固定的小红书 endpoint；平台改版时只要返回结构仍包含笔记卡片，仍可正常解析。
- 增加旧电脑兼容模式：可通过 `LAST30DAYS_BROWSER_PATH` 使用本机仍受系统支持的 Chromium/Chrome，也可用 `LAST30DAYS_DISABLE_BROWSER=1` 完全关闭浏览器并使用公开 API/搜索兜底。
- `--diagnose` 现在会显示浏览器模式、外部浏览器路径和路径是否存在，便于排查旧 macOS 的浏览器二进制兼容性。
- 版本升级至 `v3.2.0`，根目录脚本与 Agent Skills 安装载荷继续由 payload 检查保持同步。

## ✨ v3.1.0 优化内容

- 修复中文平台日期统一按北京时间（CST）归档，避免非北京时间机器上的窗口边界偏移。
- 新增 CJK bigram 回退分词，`jieba` 变为可选增强，skill 可零硬依赖运行。
- 统一 HTTP 重试退避、Retry-After 解析和 debug URL 脱敏。
- 新增 payload 生成/漂移检查、版本单源、缓存接线和 GitHub Actions CI。

## ✨ v3.0.0 升级内容

- 追平原版 v3 的 Agent Skills 包结构：`skills/last30days` 现在是可独立安装的运行载荷。
- 中文 CLI 统一使用单入口 `last30days.py`，根目录和 Skill 载荷保持同名结构。
- 新增 `--emit html` 和 `--emit html-path`，可生成离线可打开的 `report.html`。
- HTML 报告融入 [op7418/guizang-ppt-skill](https://github.com/op7418/guizang-ppt-skill) 的 Swiss/IKB 视觉语言，适合浏览、归档、打印。
- 小红书和知乎搜索增加空结果兜底说明，失败时会标注已尝试路径与可能原因。
- 抖音、头条在原生接口被风控时新增公开搜索引擎兜底，不再静默返回 0 条（见 issue #8）。
- 修复 macOS/Linux 下 `skills/last30days/SKILL.md` 损坏 symlink 导致的 `npx` 安装失败（见 issue #10）。
- 对照上游 [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill) 同步若干平台无关能力：`--as-of` 历史回溯、跨平台聚合热点、`LAST30DAYS_DEFAULT_SEARCH`/`EXCLUDE_SOURCES` 配置开关、诚实 `--diagnose`（实时探测）、HTML 报告 XSS 加固。
- 根目录 `scripts/` 继续保留，方便本地开发和旧路径调用；Agent Skills 安装使用 `skills/last30days/scripts` 下的自包含载荷。

### ✅ 发布验证

本次发布前已完成以下质检：

- 远端发布 tag 统一为 `v3.2.0`，没有额外 v3 派生 tag。
- 根目录与 Skill 载荷均统一使用 `last30days.py` 单入口，没有额外入口文件。
- 全量测试通过：`python -m pytest tests -q`，共 `214 passed`。
- 根目录入口和 Skill 载荷入口均已验证：`py scripts/last30days.py --diagnose` 与 `py skills/last30days/scripts/last30days.py --diagnose` 均可正常输出平台可用性诊断。

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

- 爬虫功能依赖 Playwright 浏览器自动化，模拟正常用户浏览行为，**不涉及**逆向加密算法或破解安全机制。
- 各平台接口随时可能变更，本项目不保证所有功能始终可用。
- 建议将请求频率控制在合理范围内（如每次搜索间隔 ≥ 5 秒），避免被平台封禁。

> 💡 **爬虫违法违规的案例频发，请务必合法合规使用。**
> 参考：[中国爬虫相关法律案例汇总](https://github.com/HiddenStrawberry/Crawler_Illegal_Cases_In_China)

---

## ✨ v2.0 新特性

### 🆕 v2.0 vs v1.0 对比

| 特性 | v1.0 | v2.0 |
|:---:|:---:|:---:|
| 免费可用平台数 | 4 个 | **7 个**（安装 Playwright 后） |
| 需要 API Key 的平台 | 微博、小红书、抖音、微信 | **仅微信**（其余可用爬虫替代） |
| 数据获取方式 | 仅 API + 公开接口 | API + **爬虫引擎** + 公开接口 |
| 安装难度 | 需配置多个 API Key | `pip install playwright` 即可 |
| marketplace.json | 缺少 owner 字段（Bug） | ✅ 已修复 |

### 核心升级

1. **集成 MediaCrawler 爬虫引擎** — 基于 Playwright 浏览器自动化，无需逆向加密算法，大幅降低使用门槛
2. **7/8 平台零配置可用** — 除微信外，所有平台均可无需 API Key 使用
3. **智能降级策略** — API 优先 → 爬虫模式 → 公开接口，三级自动降级
4. **修复 Issue #1** — 修复 marketplace.json 缺少 owner 字段导致 Claude Code 安装失败的 bug
5. **登录态缓存** — 爬虫模式支持 Cookie 持久化，减少重复登录

---

## 📋 平台支持

| 平台 | 模块 | 数据获取方式 | 需要配置 |
|:---:|:---:|:---:|:---:|
| 🔴 微博 | `weibo.py` | API / 🕷️爬虫 / 公开接口 | ✅ 爬虫模式无需配置 |
| 📕 小红书 | `xiaohongshu.py` | API / 🕷️爬虫 / 公开接口 / Bing 兜底 | ✅ 爬虫模式无需配置 |
| 📺 B站 | `bilibili.py` | 公开 API / 🕷️爬虫备用 | ✅ 无需配置 |
| 💬 知乎 | `zhihu.py` | 公开搜索 / 🕷️爬虫备用 | ✅ 无需配置 |
| 🎵 抖音 | `douyin.py` | API / 🕷️爬虫 / 公开接口 / 搜索兜底 | ✅ 爬虫模式无需配置 |
| 💚 微信 | `wechat.py` | API / 搜狗搜索 | `WECHAT_API_KEY`（可选） |
| 🔵 百度 | `baidu.py` | 公开搜索 / API | ✅ 基础搜索无需配置 |
| 📰 头条 | `toutiao.py` | 公开接口 / 搜索兜底 | ✅ 无需配置 |

> 🕷️ = 可选的 Playwright 浏览器模式（`pip install playwright && playwright install chromium`）；旧系统可使用 `LAST30DAYS_BROWSER_PATH` 或直接走公开搜索兜底。

---

## 🤖 Agent 平台安装

### Agent Skills（推荐）

```bash
npx skills add Jesseovo/last30days-skill-cn -g
```

### Cursor（推荐）

将项目克隆到 Cursor 技能目录：

```bash
git clone https://github.com/Jesseovo/last30days-skill-cn.git
```

然后在 Cursor 中将 `SKILL.md` 添加为项目技能。

### Claude Code

```bash
# 方式一：通过 Agent Skills 安装（推荐）
npx skills add Jesseovo/last30days-skill-cn -g

# 方式二：手动安装
git clone https://github.com/Jesseovo/last30days-skill-cn.git ~/.claude/skills/last30days-cn
```

### OpenClaw / ClawHub

```bash
git clone https://github.com/Jesseovo/last30days-skill-cn.git ~/.agents/skills/last30days-cn
```

### Gemini CLI

```bash
git clone https://github.com/Jesseovo/last30days-skill-cn.git
# 在 Gemini CLI 中作为扩展加载
```

### 通用 Agent

任何支持 **Bash / Read / Write** 工具的 AI Agent 都可以使用本技能。

---

## ⚙️ 配置指南

### 📍 第一步：可选增强

```bash
python -m pip install jieba
```

> `jieba` 不是硬依赖；未安装时会自动使用 CJK bigram 回退分词，仍可运行。

### 📍 第二步：安装爬虫引擎（可选，推荐，可获取 7/8 平台数据）

```bash
python -m pip install playwright
python -m playwright install chromium
```

> 安装 Playwright 后，微博、小红书、抖音、B站（备用）、知乎（备用）均可无需 API Key 使用。

### 旧 macOS / 旧电脑兼容模式

Playwright 管理的 Chromium 会随版本提高系统要求。macOS Catalina 等旧系统无法启动新版浏览器时，不需要放弃整个 skill：

1. 继续使用公开 API 和 Bing 站内搜索兜底（不安装 Playwright），或安装一份仍支持当前系统的 Chromium/Chrome。
2. 将 Playwright 指向本机浏览器可执行文件：

```bash
export LAST30DAYS_BROWSER_PATH="/Applications/Chromium.app/Contents/MacOS/Chromium"
python scripts/last30days.py --diagnose
```

也可以使用已安装的 Chrome channel：

```bash
export LAST30DAYS_BROWSER_CHANNEL=chrome
```

若希望强制跳过所有浏览器调用：

```bash
export LAST30DAYS_DISABLE_BROWSER=1
python scripts/last30days.py "AI 工具" --search weibo,xiaohongshu,bilibili,zhihu,douyin,baidu,toutiao
```

`LAST30DAYS_BROWSER_PATH` 必须指向旧系统实际能够启动的浏览器；skill 不会下载或升级系统浏览器。浏览器爬虫仍受平台登录态、验证码和接口改版影响，小红书的 `search/recommend` 联想词不会被计入搜索结果。

### 📍 第三步：创建配置文件（可选）

如果您希望使用 API 模式获取更稳定的数据，或需要使用微信公众号搜索：

```bash
mkdir -p ~/.config/last30days-cn
touch ~/.config/last30days-cn/.env
chmod 600 ~/.config/last30days-cn/.env
```

**Windows（PowerShell）等价：** 创建目录与空配置文件可用 `New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.config\last30days-cn"` 与 `New-Item -ItemType File -Path "$env:USERPROFILE\.config\last30days-cn\.env" -Force`。限制 `.env` 仅当前用户可读写可近似使用 `icacls "$env:USERPROFILE\.config\last30days-cn\.env" /inheritance:r /grant:r "$($env:USERNAME):(R,W)"`（与 Unix `chmod 600` 意图相近，权限模型不同）。

编辑 `~/.config/last30days-cn/.env`，按需填入 API Key：

```ini
# ============================================
# last30days-cn v2.0 配置文件
# ============================================
# 📌 说明：所有 API Key 均为可选
# 安装 Playwright 后，大部分平台已可通过爬虫模式使用
# API Key 提供更稳定的数据获取方式
# ============================================

# 🔴 微博开放平台（可选，已有爬虫模式替代）
# 获取方式: https://open.weibo.com → 创建应用 → 获取 Access Token
WEIBO_ACCESS_TOKEN=

# 📕 小红书（可选，已有爬虫模式替代）
# 获取方式: https://scrapecreators.com → 注册 → 获取 API Key
SCRAPECREATORS_API_KEY=

# 💬 知乎 Cookie（可选，增强搜索质量）
# 获取方式: 浏览器登录知乎 → F12 → Network → 复制 Cookie 值
ZHIHU_COOKIE=

# 🎵 抖音（可选，已有爬虫模式替代）
# 获取方式: https://tikhub.io → 注册 → 获取 API Key
TIKHUB_API_KEY=

# 💚 微信公众号搜索（目前无爬虫替代，需 API Key 才能使用）
# 获取方式: 使用第三方微信搜索 API 服务商
WECHAT_API_KEY=

# 🔵 百度搜索 API（可选，公开搜索已可用）
# 获取方式: https://cloud.baidu.com → 搜索服务 → 创建应用
BAIDU_API_KEY=
BAIDU_SECRET_KEY=
```

### 📍 第四步：验证配置

```bash
python scripts/last30days.py --diagnose
```

将输出各平台的可用状态和爬虫引擎状态：

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
    "note": "安装 Playwright 后，微博/小红书/抖音/B站/知乎可无需 API Key 使用爬虫模式"
  },
  "note_douyin_toutiao": "抖音/头条原生接口需签名参数，常被风控；接口失败时改用公开搜索引擎兜底，仅能拿到公开链接，无真实互动数据与精确日期。"
}
```

---

## 🚀 使用方式

### 基本用法

```bash
python scripts/last30days.py "AI编程助手" --emit compact
python scripts/last30days.py "AI编程助手" --emit html-path
```

### 命令行参数

| 参数 | 说明 | 示例 |
|:---:|:---:|:---:|
| `--emit` | 输出模式 | `compact` / `json` / `md` / `context` / `path` / `html` / `html-path` |
| `--quick` | 快速搜索 | 更少数据源，更快速度 |
| `--deep` | 深度搜索 | 更多数据源，更全面 |
| `--days N` | 回溯天数 | `--days 7`（最近一周） |
| `--as-of` | 历史回溯终点日期 | `--as-of 2026-05-01`（以该日为终点回溯 N 天） |
| `--search` | 指定搜索源 | `--search weibo,bilibili,zhihu` |
| `--diagnose` | 诊断配置 | 显示各平台可用状态 |
| `--timeout SECS` | 全局超时秒数 | 覆盖默认全局超时 |
| `--save-dir DIR` | 自动保存原始输出目录 | 将原始输出写入指定目录 |
| `--debug` | 调试模式 | 输出详细日志 |

> 🔧 **环境变量**：未指定 `--search` 时，回退到 `LAST30DAYS_DEFAULT_SEARCH`（逗号分隔的默认源集）；`EXCLUDE_SOURCES` 可从启用集合中排除指定源。

### 使用示例

```bash
# 🔍 搜索 AI 相关话题
python scripts/last30days.py "最新AI工具" --emit compact

# ⚡ 快速搜索，仅 B站和知乎
python scripts/last30days.py "Python教程" --quick --search bilibili,zhihu

# 📊 深度搜索并保存结果
python scripts/last30days.py "新能源汽车" --deep --save-dir ~/Documents/research

# 📋 输出 JSON 格式（适合程序处理）
python scripts/last30days.py "ChatGPT替代品" --emit json

# 🗓️ 仅搜索最近 7 天
python scripts/last30days.py "热门话题" --days 7

# 🧾 生成可离线打开的 HTML 报告
python scripts/last30days.py "具身智能" --deep --emit html-path
```

---

## 🔧 数据获取策略（三级降级）

v2.0 采用三级自动降级策略，确保最大可用性：

```
优先级 1: API 模式（如配置了 API Key）
    ↓ 失败或未配置
优先级 2: 爬虫模式（MediaCrawler，需要 Playwright）
    ↓ 失败或未安装
优先级 3: 公开接口（HTTP 直接请求，无需任何配置）
    ↓ 仍无结果（抖音/头条/小红书/知乎）
兜底: 公开搜索引擎（Bing site: 搜索，获取公开链接）
```

### 各平台数据获取方式对比

| 平台 | API 模式 | 爬虫模式 | 公开接口 | 搜索兜底 |
|:---:|:---:|:---:|:---:|:---:|
| 微博 | `WEIBO_ACCESS_TOKEN` | ✅ Playwright | ✅ m.weibo.cn | - |
| 小红书 | MCP HTTP API(可选) | ✅ Playwright (笔记 payload 识别) | ⚠️ 命中率低 | ✅ Bing |
| B站 | - | ✅ Playwright(备用) | ✅ 公开 API | - |
| 知乎 | `ZHIHU_COOKIE`(增强) | ✅ Playwright(备用) | ✅ 公开搜索 | ✅ Bing |
| 抖音 | `TIKHUB_API_KEY` | ✅ Playwright | ⚠️ 需签名 | ✅ Bing |
| 微信 | `WECHAT_API_KEY` | - | ✅ 搜狗搜索 | - |
| 百度 | `BAIDU_API_KEY` | - | ⚠️ 公开搜索可能被拦截 | ✅ Bing |
| 头条 | - | - | ⚠️ 需签名 | ✅ Bing |

> ⚠️ 抖音/头条原生 web 接口现在强制要求签名参数（`a_bogus` / `_signature`），常被风控。接口失败时改用公开搜索引擎兜底，**只能拿到公开链接，无真实互动数据与精确日期**。

---

## 🏗️ 项目架构

```
last30days-skill-cn/
├── 📄 SKILL.md              # Agent 技能定义文件
├── 📄 README.md             # 项目说明（中文，本文件）
├── 📄 README.en.md          # 项目说明（English）
├── 📄 LICENSE               # MIT 许可证
├── 📄 requirements.txt      # Python 依赖
├── 📁 assets/               # README 配图
├── 📁 scripts/
│   ├── 🐍 last30days.py     # 中文主入口 CLI
│   └── 📁 lib/
│       ├── crawler_bridge.py  # 🆕 MediaCrawler 爬虫桥接模块
│       ├── weibo.py          # 微博搜索模块
│       ├── xiaohongshu.py    # 小红书搜索模块
│       ├── bilibili.py       # B站搜索模块
│       ├── zhihu.py          # 知乎搜索模块
│       ├── douyin.py         # 抖音搜索模块
│       ├── wechat.py         # 微信公众号模块
│       ├── baidu.py          # 百度搜索模块
│       ├── toutiao.py        # 今日头条模块
│       ├── schema.py         # 数据结构定义
│       ├── score.py          # 评分系统
│       ├── normalize.py      # 数据标准化
│       ├── dedupe.py         # 去重
│       ├── render.py         # 输出渲染
│       ├── relevance.py      # 相关性计算
│       ├── query.py          # 查询预处理
│       ├── query_type.py     # 查询类型检测
│       ├── entity_extract.py # 实体抽取
│       ├── env.py            # 环境配置管理
│       ├── cache.py          # 缓存管理
│       ├── dates.py          # 日期工具
│       ├── http.py           # HTTP 客户端
│       ├── ui.py             # 终端 UI
│       └── setup_wizard.py   # 配置向导
├── 📁 skills/
│   └── 📁 last30days/        # Agent Skills 自包含运行载荷
│       ├── 📄 SKILL.md       # 安装后供 Agent 读取的技能说明
│       └── 📁 scripts/
│           ├── 🐍 last30days.py
│           └── 📁 lib/       # 与根目录脚本同步的运行依赖
├── 📁 fixtures/              # 示例数据
├── 📁 tests/                 # 测试用例
└── 📁 hooks/                 # Agent 钩子
```

---

## 📊 评分系统

每条搜索结果的综合评分（0-100）基于：

| 维度 | 权重 | 说明 |
|:---:|:---:|:---|
| 🎯 相关性 | 45% | 与查询主题的文本匹配度 |
| 🕐 时效性 | 25% | 内容发布时间的新鲜程度 |
| 🔥 互动度 | 30% | 各平台互动指标（见下表） |

### 各平台互动指标

| 平台 | 互动指标 |
|:---:|:---|
| 微博 | 转发 + 评论 + 点赞 |
| 小红书 | 点赞 + 收藏 + 评论 + 分享 |
| B站 | 播放 + 弹幕 + 评论 + 投币 + 收藏 |
| 知乎 | 赞同 + 评论 + 收藏 |
| 抖音 | 点赞 + 评论 + 分享 + 播放 |
| 头条 | 评论 + 阅读 + 点赞 |

---

## 🙏 致谢

- [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill) — 原始英文版项目
- [NanmiCoder/MediaCrawler](https://github.com/NanmiCoder/MediaCrawler) — 爬虫引擎技术灵感来源

---

## 📜 许可证

本项目基于 [MIT License](LICENSE) 发布。

- 🔗 原始项目: [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill) by Matt Van Horn
- 🇨🇳 中文本土化: Jesse ([@Jesseovo](https://github.com/Jesseovo))
