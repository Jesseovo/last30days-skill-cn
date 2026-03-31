#!/bin/bash
# Author: Jesse (https://github.com/ChiTing111)
set -euo pipefail

# 检查 last30days-cn 配置状态并显示欢迎/就绪信息（中国平台）。
# 优先级：.claude/last30days-cn.env > ~/.config/last30days-cn/.env > 环境变量

PROJECT_ENV=".claude/last30days-cn.env"
GLOBAL_ENV="$HOME/.config/last30days-cn/.env"

# 可选：配置文件权限过宽时警告
check_perms() {
  local file="$1"
  if [[ ! -f "$file" ]]; then return; fi
  local perms
  perms=$(stat -f '%Lp' "$file" 2>/dev/null || stat -c '%a' "$file" 2>/dev/null || echo "")
  if [[ -n "$perms" && "$perms" != "600" && "$perms" != "400" ]]; then
    echo "last30days-cn：警告 — $file 权限为 $perms（建议 600）。"
    echo "  修复：chmod 600 $file"
  fi
}

# 将 env 文件读入变量供检查（不 export）
load_env_vars() {
  local file="$1"
  if [[ -f "$file" ]]; then
    while IFS='=' read -r key value; do
      [[ "$key" =~ ^[[:space:]]*# ]] && continue
      [[ -z "$key" ]] && continue
      key=$(echo "$key" | xargs)
      value=$(echo "$value" | xargs | sed 's/^["'\''"]//;s/["'\''"]$//')
      if [[ -n "$key" && -n "$value" ]]; then
        eval "ENV_${key}=\"${value}\""
      fi
    done < "$file"
  fi
}

CONFIG_FILE=""
if [[ -f "$PROJECT_ENV" ]]; then
  CONFIG_FILE="$PROJECT_ENV"
  check_perms "$PROJECT_ENV"
elif [[ -f "$GLOBAL_ENV" ]]; then
  CONFIG_FILE="$GLOBAL_ENV"
  check_perms "$GLOBAL_ENV"
fi

if [[ -n "$CONFIG_FILE" ]]; then
  load_env_vars "$CONFIG_FILE"
fi

SETUP_COMPLETE="${ENV_SETUP_COMPLETE:-${SETUP_COMPLETE:-}}"

# 中国平台可选密钥（文件或环境）
HAS_WEIBO="${ENV_WEIBO_ACCESS_TOKEN:-${WEIBO_ACCESS_TOKEN:-}}"
HAS_SCRAPE="${ENV_SCRAPECREATORS_API_KEY:-${SCRAPECREATORS_API_KEY:-}}"
HAS_ZHIHU_COOKIE="${ENV_ZHIHU_COOKIE:-${ZHIHU_COOKIE:-}}"
HAS_TIKHUB="${ENV_TIKHUB_API_KEY:-${TIKHUB_API_KEY:-}}"
HAS_WECHAT="${ENV_WECHAT_API_KEY:-${WECHAT_API_KEY:-}}"
HAS_BAIDU="${ENV_BAIDU_API_KEY:-${BAIDU_API_KEY:-}}"

any_cn_key_set() {
  [[ -n "$HAS_WEIBO" || -n "$HAS_SCRAPE" || -n "$HAS_ZHIHU_COOKIE" || -n "$HAS_TIKHUB" || -n "$HAS_WECHAT" || -n "$HAS_BAIDU" ]]
}

# 从未配置且无密钥：中文欢迎
if [[ -z "$SETUP_COMPLETE" && -z "$CONFIG_FILE" ]] && ! any_cn_key_set; then
  cat <<'EOF'
last30days-cn：已就绪。运行研究流程即可开始 — 配置可选密钥可解锁更多平台。

B站、知乎、百度（基础）、今日头条 可免费直接使用，无需 API Key。
配置 WEIBO_ACCESS_TOKEN、SCRAPECREATORS_API_KEY、ZHIHU_COOKIE、TIKHUB_API_KEY、WECHAT_API_KEY、BAIDU_API_KEY 可分别启用或增强 微博、小红书、知乎、抖音、微信公众号、百度搜索 等能力。
EOF
  exit 0
fi

# 基础可用源：四大免费平台
SOURCE_COUNT=4

[[ -n "$HAS_WEIBO" ]] && SOURCE_COUNT=$((SOURCE_COUNT + 1))
[[ -n "$HAS_SCRAPE" ]] && SOURCE_COUNT=$((SOURCE_COUNT + 1))
[[ -n "$HAS_ZHIHU_COOKIE" ]] && SOURCE_COUNT=$((SOURCE_COUNT + 1))
[[ -n "$HAS_TIKHUB" ]] && SOURCE_COUNT=$((SOURCE_COUNT + 1))
[[ -n "$HAS_WECHAT" ]] && SOURCE_COUNT=$((SOURCE_COUNT + 1))
[[ -n "$HAS_BAIDU" ]] && SOURCE_COUNT=$((SOURCE_COUNT + 1))

echo "last30days-cn：就绪 — 当前约 ${SOURCE_COUNT} 路数据源可用（含 B站/知乎/百度基础/头条 等免费源）。"
if ! any_cn_key_set; then
  echo "  提示：在 ~/.config/last30days-cn/.env 或 .claude/last30days-cn.env 中配置可选密钥，可启用微博、小红书、抖音等更多平台。"
fi
