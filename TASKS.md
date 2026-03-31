# last30days-cn 本地化任务清单

> Author: Jesse

以下为 **中国平台 fork** 相关任务，均已完成。

## 产品与文档

- [x] 编写中文 `README.md`（平台表、多 Agent 安装、配置、示例）
- [x] 编写中文 `CLAUDE.md`（Agent 指引）
- [x] 编写中文 `SPEC.md`（架构、模块、CLI、输出路径）
- [x] 编写中文 `TASKS.md`（本清单）
- [x] 更新 `SKILL.md` 与技能 frontmatter（若适用）
- [x] 中文 `release-notes.md`（v1.0.0）

## 核心编排与 CLI

- [x] `scripts/last30days.py` 改造为多源中文编排（并行、超时档位、`--search` / `--days` / `--emit` 等）
- [x] 移除或替换英文源依赖，统一为 8 大中文平台流水线
- [x] `setup` 主题入口与 `setup_wizard` 集成
- [x] `--diagnose` 数据源可用性诊断
- [x] `--save-dir` 额外落盘 Markdown
- [x] Windows UTF-8 输出适配

## 平台适配层（8 个）

- [x] `scripts/lib/weibo.py` — 微博
- [x] `scripts/lib/xiaohongshu.py` — 小红书
- [x] `scripts/lib/bilibili.py` — B 站
- [x] `scripts/lib/zhihu.py` — 知乎
- [x] `scripts/lib/douyin.py` — 抖音
- [x] `scripts/lib/wechat.py` — 微信公众号
- [x] `scripts/lib/baidu.py` — 百度搜索
- [x] `scripts/lib/toutiao.py` — 今日头条

## 通用库模块

- [x] `env.py` — `last30days-cn` 配置路径与密钥集合
- [x] `dates.py` — 日期窗口
- [x] `cache.py` — TTL 缓存
- [x] `http.py` — HTTP 与重试
- [x] `normalize.py` — 八平台归一化与日期过滤
- [x] `score.py` — 打分与排序、`relevance_filter`
- [x] `dedupe.py` — 去重与跨源关联
- [x] `render.py` — 输出与写盘路径
- [x] `schema.py` — 报告模型
- [x] `query.py` — 查询处理（jieba）
- [x] `relevance.py` — 相关性（jieba 中文分支）
- [x] `entity_extract.py` — 实体相关逻辑
- [x] `query_type.py` — 查询类型检测
- [x] `ui.py` — 状态与展示辅助

## 包规范

- [x] `scripts/lib/__init__.py` 保持裸包标记（仅注释，无 eager import）

## 依赖与中文 NLP

- [x] `requirements.txt` 加入 `jieba` 等必要依赖

## 测试与样例

- [x] 针对中文流水线调整或新增测试与 fixtures（随仓库现状）
- [x] 验证 `--emit=compact` / `--emit=context` 等主路径

## 发布与同步

- [x] `scripts/sync.sh` 或与 Claude Code / OpenClaw 目录的部署说明对齐（按需手动改目标目录名）

---

*凡上列项均为回顾性勾选，表示本 fork 规划内工作已落实；若上游 last30days 继续演进，可另开 TASKS 跟踪合并。*
