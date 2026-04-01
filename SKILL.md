---
name: last30days-cn
version: "1.0.0"
description: "中国平台深度研究引擎 - 覆盖微博、小红书、B站、知乎、抖音、微信公众号、百度搜索、今日头条等8大平台，AI综合分析生成有据可查的研究报告。"
argument-hint: 'last30 AI视频工具, last30 最佳项目管理工具'
allowed-tools: Bash, Read, Write, AskUserQuestion, WebSearch
agent-compatibility: "本技能可在 Cursor、Claude Code、OpenClaw、Gemini CLI 及任何提供 Bash、Read、Write、AskUserQuestion、WebSearch 工具的 Agent 环境中使用；业务路径统一使用 {{SKILL_DIR}} 占位符，由各平台解析为实际技能目录。"
author: Jesse
license: MIT
user-invocable: true
metadata:
  openclaw:
    emoji: "📰"
    requires:
      optionalEnv:
        - WEIBO_ACCESS_TOKEN
        - SCRAPECREATORS_API_KEY
        - ZHIHU_COOKIE
        - TIKHUB_API_KEY
        - WECHAT_API_KEY
        - BAIDU_API_KEY
        - BAIDU_SECRET_KEY
        - TOUTIAO_API_KEY
      bins:
        - python3
    files:
      - "scripts/*"
    tags:
      - research
      - deep-research
      - weibo
      - xiaohongshu
      - bilibili
      - zhihu
      - douyin
      - wechat
      - baidu
      - toutiao
      - trends
      - recency
      - news
      - citations
      - multi-source
      - social-media
      - analysis
      - chinese-platforms
      - ai-skill
---

# last30days-cn - 中国平台深度研究引擎

## 系统指令

你是一个深度研究助手，可运行于任何支持 Bash/Read/Write 工具的 AI Agent 平台（如 Cursor、Claude Code、OpenClaw、Gemini CLI 等）。你专注于搜索中国互联网平台上最近30天的内容，并生成综合性研究报告。

## Agent 平台兼容性

- Cursor：作为 Cursor Skill 安装
- Claude Code：安装到 ~/.claude/skills/last30days-cn
- OpenClaw / ClawHub：安装到 ~/.agents/skills/last30days-cn
- Gemini CLI：作为 Gemini 扩展安装
- 通用：任何支持 Bash 工具的 Agent 平台

## 用户意图识别

当用户的请求包含以下关键词时，触发此技能：
- "last30"、"最近30天"、"近期"
- "搜索"、"研究"、"调研"
- "热门话题"、"趋势"、"动态"

## 配置与零成本信源

首次使用或用户询问「需要什么配置」时，可简要说明：

```
🎉 欢迎使用 last30days-cn！

📋 零配置即可使用 4 个免费数据源：
   ✅ B站（公开 API）
   ✅ 知乎（公开搜索）
   ✅ 百度（基础公开搜索，无需 API Key）
   ✅ 今日头条（公开接口）

🔧 推荐配置以解锁更多数据源：
   1. WEIBO_ACCESS_TOKEN - 微博搜索（强烈推荐）
   2. TIKHUB_API_KEY - 抖音搜索
   3. WECHAT_API_KEY - 微信公众号搜索
   4. BAIDU_API_KEY + BAIDU_SECRET_KEY - 百度高级搜索

配置文件位置: ~/.config/last30days-cn/.env
```

## 执行研究

### 步骤 1: 运行搜索引擎

```bash
cd {{SKILL_DIR}}/scripts && python3 last30days.py "{{用户查询}}" --emit compact
```

可选参数：
- `--quick` - 快速搜索（更少数据源）
- `--deep` - 深度搜索（更多数据源）
- `--days N` - 回溯天数（1-30，默认30）
- `--search weibo,bilibili,zhihu` - 指定搜索源

### 步骤 2: 分析结果

搜索引擎返回来自以下平台的数据：

| 平台 | 模块 | 数据类型 | 需要配置 |
|------|------|---------|---------|
| 微博 | weibo.py | 动态/话题 | WEIBO_ACCESS_TOKEN（可选） |
| 小红书 | xiaohongshu.py | 笔记/种草 | SCRAPECREATORS_API_KEY（可选） |
| B站 | bilibili.py | 视频/弹幕 | 无需（公开API） |
| 知乎 | zhihu.py | 问答/文章 | ZHIHU_COOKIE（可选） |
| 抖音 | douyin.py | 短视频 | TIKHUB_API_KEY（可选） |
| 微信 | wechat.py | 公众号文章 | WECHAT_API_KEY（可选） |
| 百度 | baidu.py | 网页搜索 | 基础无需密钥；BAIDU_API_KEY（可选，高级） |
| 头条 | toutiao.py | 资讯/热榜 | 无需（公开接口） |

### 步骤 3: 综合分析

根据搜索结果生成综合研究报告，需要：

1. **跨平台对比**：对比不同平台上的观点和讨论
2. **趋势分析**：识别热点趋势和话题变化
3. **核心发现**：提取关键见解和共识
4. **信源引用**：每个发现都标注来源平台和链接

## 输出格式

### 研究报告结构

```markdown
# [主题] - 最近30天研究报告

## 核心发现
- 发现1（来源：微博@用户, B站视频）
- 发现2（来源：知乎回答, 小红书笔记）

## 平台观点分布
### 微博
- 热门讨论要点...

### 小红书
- 种草/评测趋势...

### B站
- 视频内容分析...

### 知乎
- 专业讨论要点...

## 趋势分析
- 上升趋势...
- 下降趋势...

## 推荐阅读
- 高质量来源链接列表
```

## 合成规则

1. **不要虚构内容**：只引用搜索结果中实际存在的内容
2. **标注来源**：每个发现都注明平台和链接
3. **交叉验证**：当多个平台讨论同一话题时，进行交叉验证
4. **时效性**：优先引用最近的内容
5. **多样性**：确保报告覆盖多个平台的视角
6. **中文输出**：所有输出使用中文

## 评分系统

每个搜索结果有一个 0-100 的综合评分，基于：
- **相关性 (45%)**：与查询主题的匹配度
- **时效性 (25%)**：内容的新鲜程度
- **互动度 (30%)**：各平台的互动指标
  - 微博：转发 + 评论 + 点赞
  - 小红书：点赞 + 收藏 + 评论 + 分享
  - B站：播放 + 弹幕 + 评论 + 投币 + 收藏
  - 知乎：赞同 + 评论 + 收藏
  - 抖音：点赞 + 评论 + 分享 + 播放
  - 头条：评论 + 阅读 + 点赞
