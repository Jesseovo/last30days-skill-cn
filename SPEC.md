# last30days-cn 技术规格说明

> Author: Jesse (https://github.com/ChiTing111)

## 概述

**last30days-cn** 是一套面向中文互联网的 **多源研究流水线**：用户给定主题后，编排器在可配置的时间窗口（默认 30 天）内并行请求多个平台适配层，将原始条目归一到统一 schema，再经相关性、互动与时间衰减等规则打分，跨源去重与轻量关联，最终生成 **终端输出**（`compact` / `json` / `md` / `context` / `path`）并落盘 **`report.md`、`report.json`、`last30days.context.md`**。

与英文版 last30days 不同，本分支 **不包含** Reddit / X / YouTube 等英文源，而由上述 8 个中文平台模块与中文 NLP（**jieba** 分词，用于 `query` / `relevance`）支撑检索与排序质量。

---

## 平台模块（8 个）

| 文件 | 平台 |
|------|------|
| `weibo.py` | 微博 |
| `xiaohongshu.py` | 小红书 |
| `bilibili.py` | B 站（哔哩哔哩） |
| `zhihu.py` | 知乎 |
| `douyin.py` | 抖音 |
| `wechat.py` | 微信公众号 |
| `baidu.py` | 百度搜索 |
| `toutiao.py` | 今日头条 |

各模块负责该平台下的搜索/抓取入口，并与 `normalize.py`、`score.py`、`dedupe.py` 对接。

---

## 核心通用模块

| 模块 | 职责摘要 |
|------|-----------|
| `env.py` | 加载 `~/.config/last30days-cn/.env`、项目级 `.claude/last30days-cn.env` 及环境变量，汇总各平台 API Key / Cookie 可用性判断 |
| `dates.py` | 日期范围计算、与时间窗口相关的辅助逻辑 |
| `cache.py` | 可选工具模块：基于 TTL 的缓存（供扩展或脚本复用；主 CLI 流水线不依赖） |
| `http.py` | 带重试的 HTTP 客户端（stdlib 为主） |
| `normalize.py` | 将各平台原始条目转为统一内部结构，并按日期窗口过滤 |
| `score.py` | 互动、时间、查询类型等维度的打分与排序 |
| `dedupe.py` | 近重复检测与跨源 `cross_refs` 关联 |
| `render.py` | 生成 compact / 全文 MD / context 片段，并写入输出目录 |
| `schema.py` | 报告与条目的数据模型、`to_dict` 等 |
| `query.py` | 查询解析、扩展（含 jieba 中文分词路径） |
| `relevance.py` | 文本相关性（含中文 jieba 分词分支） |
| `entity_extract.py` | 可选工具模块：实体或短语级抽取（供测试与扩展；主 CLI 流水线不依赖） |
| `query_type.py` | 查询类型检测，影响部分源的排序权重 |

**辅助模块**（与 CLI / 运维相关）：`ui.py`、`setup_wizard.py` 等，详见 `scripts/lib/` 目录列表。

---

## CLI 参考：`scripts/last30days.py`

```text
python3 scripts/last30days.py <topic> [选项]

位置参数:
  topic                 研究主题（多个词以空格分隔）；特殊值 setup 进入配置向导

选项:
  --emit MODE           输出模式: compact | json | md | context | path（默认: compact）
  --quick               快速模式：更短超时、更少深度
  --deep                深度模式：更长超时、更深抓取
  --debug               调试日志（设置 LAST30DAYS_DEBUG）
  --days N              回溯天数，1–30（默认: 30）
  --diagnose            打印各数据源可用性 JSON 后退出（不执行完整研究）
  --timeout SECS        全局超时秒数（覆盖当前 depth 档位的默认值）
  --search SOURCES      逗号分隔平台子集，例如 weibo,xhs,bilibili,zhihu,douyin,wechat,baidu,toutiao
                        （小红书可写 xiaohongshu 或别名 xhs）
  --save-dir DIR        将 compact + 源状态额外写入指定目录下的 Markdown 文件
```

**说明：**

- Windows 下脚本会对 stdout/stderr 做 UTF-8 配置，避免中文乱码。  
- `--search` 未指定时，默认尝试全部 8 源（具体是否返回数据取决于密钥与网络）。  
- `topic` 为 `setup`（不区分大小写）时走 `setup_wizard`，不写研究报告。

---

## 输出目录

默认目录：

```text
~/.local/share/last30days/out/
```

主要文件：

- `report.md` — 完整 Markdown 报告  
- `report.json` — 归一化后的结构化报告  
- `last30days.context.md` — 供其他 Skill / 提示词引用的精简上下文  

可通过环境变量 **`LAST30DAYS_OUTPUT_DIR`** 覆盖目录；若主目录无写权限，`render.py` 可能回退到临时目录下的 `last30days/out`（见实现）。

---

## 配置路径（摘要）

- 全局：`~/.config/last30days-cn/.env`  
- 可选项目级：向上查找 `.claude/last30days-cn.env`  
- 目录覆盖：`LAST30DAYS_CN_CONFIG_DIR` / `LAST30DAYS_CONFIG_DIR`  

完整键名以 `scripts/lib/env.py` 中 `get_config()` 为准。
