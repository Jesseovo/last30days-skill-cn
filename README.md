# 📰 last30days-cn — 中国平台深度研究引擎

> 🚀 30 天的研究，30 秒的结果。8 大平台。零过时信息。

**last30days-cn** 是一个 AI Agent 技能（Skill），能够自动搜索中国互联网 8 大主流平台最近 30 天的内容，综合分析后生成有据可查的研究报告。

🔗 本项目基于 [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill) 进行深度本土化改造，完全面向中国用户和中文互联网平台。

👤 **作者 / Author:** Jesse ([@ChiTing111](https://github.com/ChiTing111))

---

## ✨ 核心特性

- 🔍 **8 大中国平台覆盖** — 微博、小红书、B站、知乎、抖音、微信公众号、百度搜索、今日头条
- 🤖 **多 Agent 平台兼容** — 支持 Cursor、Claude Code、OpenClaw、Gemini CLI 等
- 🇨🇳 **中文 NLP** — 基于 jieba 分词，中文停用词、同义词扩展
- 📊 **智能评分** — 相关性 45% + 时效性 25% + 互动度 30% 综合评分
- 🔄 **跨平台对比** — 自动关联多平台相同话题，交叉验证
- ⚡ **4 个免费源** — B站、知乎、百度（基础公开搜索）、今日头条无需 API Key 即可使用

---

## 📋 平台支持

| 平台 | 模块 | 数据类型 | 需要配置 |
|:---:|:---:|:---:|:---:|
| 🔴 微博 | `weibo.py` | 动态/话题 | `WEIBO_ACCESS_TOKEN`（可选） |
| 📕 小红书 | `xiaohongshu.py` | 笔记/种草 | `SCRAPECREATORS_API_KEY`（可选） |
| 📺 B站 | `bilibili.py` | 视频/弹幕 | ✅ 无需（公开 API） |
| 💬 知乎 | `zhihu.py` | 问答/文章 | `ZHIHU_COOKIE`（可选） |
| 🎵 抖音 | `douyin.py` | 短视频 | `TIKHUB_API_KEY`（可选） |
| 💚 微信 | `wechat.py` | 公众号文章 | `WECHAT_API_KEY`（可选） |
| 🔵 百度 | `baidu.py` | 网页搜索 | ✅ 基础搜索无需密钥；`BAIDU_API_KEY`（可选，高级） |
| 📰 头条 | `toutiao.py` | 资讯/热榜 | ✅ 无需（公开接口） |

---

## 🤖 Agent 平台安装

### Cursor（推荐）

将项目克隆到 Cursor 技能目录：

```bash
git clone https://github.com/ChiTing111/last30days-skill-cn.git
```

然后在 Cursor 中将 `SKILL.md` 添加为项目技能。

### Claude Code

```bash
git clone https://github.com/ChiTing111/last30days-skill-cn.git ~/.claude/skills/last30days-cn
```

### OpenClaw / ClawHub

```bash
git clone https://github.com/ChiTing111/last30days-skill-cn.git ~/.agents/skills/last30days-cn
```

### Gemini CLI

```bash
git clone https://github.com/ChiTing111/last30days-skill-cn.git
# 在 Gemini CLI 中作为扩展加载
```

### 通用 Agent

任何支持 **Bash / Read / Write** 工具的 AI Agent 都可以使用本技能。

---

## ⚙️ 配置指南

### 📍 第一步：安装依赖

```bash
pip install jieba
```

### 📍 第二步：创建配置文件

```bash
mkdir -p ~/.config/last30days-cn
touch ~/.config/last30days-cn/.env
chmod 600 ~/.config/last30days-cn/.env
```

### 📍 第三步：配置 API Key

编辑 `~/.config/last30days-cn/.env`，按需填入以下 API Key：

```ini
# ============================================
# last30days-cn 配置文件
# ============================================
# 作者: Jesse (https://github.com/ChiTing111)
#
# 📌 说明：所有配置均为可选
# B站、知乎、百度（基础）、今日头条无需 API Key 即可使用
# 配置更多 API Key 可解锁更多数据源
# ============================================

# 🔴 微博开放平台
# 获取方式: https://open.weibo.com → 创建应用 → 获取 Access Token
WEIBO_ACCESS_TOKEN=

# 📕 小红书（通过 ScrapeCreators 聚合 API）
# 获取方式: https://scrapecreators.com → 注册 → 获取 API Key
# 💡 同一个 Key 也支持抖音搜索
SCRAPECREATORS_API_KEY=

# 💬 知乎 Cookie（增强搜索，非必需）
# 获取方式: 浏览器登录知乎 → F12 → Network → 复制 Cookie 值
ZHIHU_COOKIE=

# 🎵 抖音（通过 TikHub API）
# 获取方式: https://tikhub.io → 注册 → 获取 API Key
TIKHUB_API_KEY=

# 💚 微信公众号搜索
# 获取方式: 使用第三方微信搜索 API 服务商
WECHAT_API_KEY=

# 🔵 百度搜索 API（高级搜索）
# 获取方式: https://cloud.baidu.com → 搜索服务 → 创建应用
# 💡 需要同时配置 API Key 和 Secret Key
BAIDU_API_KEY=
BAIDU_SECRET_KEY=

# 📰 今日头条 API（可选，公开接口已可用）
TOUTIAO_API_KEY=

# ✅ 配置完成标记（自动设置）
# SETUP_COMPLETE=true
```

### 📍 第四步：验证配置

```bash
python scripts/last30days.py --diagnose
```

将输出各平台的可用状态：

```json
{
  "weibo": false,
  "xiaohongshu": false,
  "bilibili": true,    // ✅ 无需配置
  "zhihu": true,        // ✅ 无需配置
  "douyin": false,
  "wechat": false,
  "baidu_api": false,
  "toutiao": true       // ✅ 无需配置
}
```

---

## 🚀 使用方式

### 基本用法

```bash
python scripts/last30days.py "AI编程助手" --emit compact
```

### 命令行参数

| 参数 | 说明 | 示例 |
|:---:|:---:|:---:|
| `--emit` | 输出模式 | `compact` / `json` / `md` / `context` / `path` |
| `--quick` | 快速搜索 | 更少数据源，更快速度 |
| `--deep` | 深度搜索 | 更多数据源，更全面 |
| `--days N` | 回溯天数 | `--days 7`（最近一周） |
| `--search` | 指定搜索源 | `--search weibo,bilibili,zhihu` |
| `--diagnose` | 诊断配置 | 显示各平台可用状态 |
| `--debug` | 调试模式 | 输出详细日志 |

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
```

---

## 🏗️ 项目架构

```
last30days-skill-cn/
├── 📄 SKILL.md              # Agent 技能定义文件
├── 📄 README.md             # 项目说明（本文件）
├── 📄 LICENSE               # MIT 许可证
├── 📄 requirements.txt      # Python 依赖
├── 📁 scripts/
│   ├── 🐍 last30days.py     # 主入口 CLI
│   └── 📁 lib/
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

## 📜 许可证

本项目基于 [MIT License](LICENSE) 发布。

- 🔗 原始项目: [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill) by Matt Van Horn
- 🇨🇳 中文本土化: Jesse ([@ChiTing111](https://github.com/ChiTing111))

---

---

# 📰 last30days-cn — Chinese Platform Deep Research Engine

> 🚀 30 days of research. 30 seconds of work. 8 platforms. Zero stale info.

**last30days-cn** is an AI Agent skill that automatically searches 8 major Chinese internet platforms for the last 30 days of content and generates well-cited research reports.

🔗 This project is a Chinese-localized fork of [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill), fully adapted for Chinese users and platforms.

👤 **Author:** Jesse ([@ChiTing111](https://github.com/ChiTing111))

---

## ✨ Key Features

- 🔍 **8 Chinese Platforms** — Weibo, Xiaohongshu, Bilibili, Zhihu, Douyin, WeChat, Baidu, Toutiao
- 🤖 **Multi-Agent Compatible** — Works with Cursor, Claude Code, OpenClaw, Gemini CLI, and more
- 🇨🇳 **Chinese NLP** — jieba-based word segmentation, Chinese stopwords, synonym expansion
- 📊 **Smart Scoring** — Relevance 45% + Recency 25% + Engagement 30%
- 🔄 **Cross-Platform Linking** — Auto-links same topics across platforms
- ⚡ **4 Free Sources** — Bilibili, Zhihu, Baidu (basic public search), and Toutiao work without API keys

---

## 📋 Supported Platforms

| Platform | Module | Data Type | Config Required |
|:---:|:---:|:---:|:---:|
| 🔴 Weibo | `weibo.py` | Posts/Topics | `WEIBO_ACCESS_TOKEN` (optional) |
| 📕 Xiaohongshu | `xiaohongshu.py` | Notes/Reviews | `SCRAPECREATORS_API_KEY` (optional) |
| 📺 Bilibili | `bilibili.py` | Videos/Danmaku | ✅ Free (public API) |
| 💬 Zhihu | `zhihu.py` | Q&A/Articles | `ZHIHU_COOKIE` (optional) |
| 🎵 Douyin | `douyin.py` | Short Videos | `TIKHUB_API_KEY` (optional) |
| 💚 WeChat | `wechat.py` | Official Account Articles | `WECHAT_API_KEY` (optional) |
| 🔵 Baidu | `baidu.py` | Web Search | ✅ Basic search free; `BAIDU_API_KEY` (optional, advanced) |
| 📰 Toutiao | `toutiao.py` | News/Trending | ✅ Free (public API) |

---

## 🚀 Quick Start

### Installation

```bash
git clone https://github.com/ChiTing111/last30days-skill-cn.git
cd last30days-skill-cn
pip install jieba
```

### Configuration

```bash
mkdir -p ~/.config/last30days-cn
# Edit ~/.config/last30days-cn/.env with your API keys (all optional)
```

### Usage

```bash
python scripts/last30days.py "AI tools" --emit compact
python scripts/last30days.py --diagnose   # Check platform availability
```

### Agent Installation

| Agent Platform | Installation Path |
|:---:|:---|
| **Cursor** | Clone and add SKILL.md as project skill |
| **Claude Code** | `~/.claude/skills/last30days-cn` |
| **OpenClaw** | `~/.agents/skills/last30days-cn` |
| **Gemini CLI** | Load as Gemini extension |
| **General** | Any agent with Bash/Read/Write tools |

---

## 📜 License

This project is licensed under the [MIT License](LICENSE).

- 🔗 Original: [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill) by Matt Van Horn
- 🇨🇳 Chinese Fork: Jesse ([@ChiTing111](https://github.com/ChiTing111))
