# last30days-cn 技能

> Author: Jesse (https://github.com/ChiTing111)

面向 Agent 的简短指引：**中国平台深度研究引擎**（微博、小红书、B 站、知乎、抖音、微信公众号、百度、今日头条），默认聚焦近 **30 天** 内容，经打分与去重后输出简报。

## 结构

- `scripts/last30days.py` — 主流程：多源并行搜索、归一化、排序、去重、写报告  
- `scripts/lib/` — 平台适配与通用能力（`env`、`http`、`normalize`、`score`、`render` 等）  
- `SKILL.md` — 对外技能定义（部署到各 Agent 的 skills 目录时使用）

## 命令

```bash
# 研究主题（默认 compact 输出）
python3 scripts/last30days.py "你的主题" --emit=compact

# 可选：同步到本机 skills 目录（路径见 scripts/sync.sh 内 TARGETS）
bash scripts/sync.sh
```

## 规则

- `scripts/lib/__init__.py` 必须为**裸包标记**（仅注释，**禁止**在包内做 eager import）。  
- 修改代码后若需部署到 `~/.claude` / `~/.agents` 等，执行 `bash scripts/sync.sh`（可按需改脚本中的目标目录名以匹配 `last30days-cn`）。

## 配置

密钥与选项见 `~/.config/last30days-cn/.env`，细节以 `scripts/lib/env.py` 为准。
