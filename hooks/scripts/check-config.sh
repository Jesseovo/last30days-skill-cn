#!/bin/bash
# Author: Jesse (https://github.com/Jesseovo)
# SessionStart hook: 显示 last30days-cn 的配置/登录态就绪信息（中国平台）。
# 优先级：.claude/last30days-cn.env > ~/.config/last30days-cn/.env > 环境变量
#
# 安全：.env 文件只按 KEY=VALUE 解析，不经过 eval / source。
# （v3 使用 eval，仓库自带的 .claude/last30days-cn.env 可借此在会话启动时执行命令）
set -euo pipefail

PROJECT_ENV=".claude/last30days-cn.env"
CONFIG_DIR="${LAST30DAYS_CN_CONFIG_DIR:-$HOME/.config/last30days-cn}"
GLOBAL_ENV="$CONFIG_DIR/.env"
COOKIE_DIR="$CONFIG_DIR/browser_cookies"

KNOWN_KEYS=" SETUP_COMPLETE WEIBO_ACCESS_TOKEN WEIBO_COOKIE ZHIHU_COOKIE BILIBILI_COOKIE TIKHUB_API_KEY DOUYIN_API_KEY WECHAT_API_KEY BAIDU_API_KEY XIAOHONGSHU_API_BASE GITHUB_TOKEN "

check_perms() {
  local file="$1"
  [[ -f "$file" ]] || return 0
  case "$(uname -s 2>/dev/null)" in MINGW*|MSYS*|CYGWIN*) return 0 ;; esac  # no POSIX modes on Windows
  local perms
  # GNU stat first: on Linux `stat -f` means --file-system and prints unrelated output.
  perms=$(stat -c '%a' "$file" 2>/dev/null || stat -f '%Lp' "$file" 2>/dev/null || echo "")
  if [[ -n "$perms" && "$perms" != "600" && "$perms" != "400" ]]; then
    echo "last30days-cn：警告 — $file 权限为 $perms（建议 600）。修复：chmod 600 $file"
  fi
}

# Safely read KEY=VALUE pairs for known keys into ENV_<KEY> variables.
load_env_vars() {
  local file="$1" line key value
  [[ -f "$file" ]] || return 0
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"
    [[ "$line" =~ ^[[:space:]]*(#|$) ]] && continue
    line="${line#export }"
    [[ "$line" == *=* ]] || continue
    key="${line%%=*}"
    value="${line#*=}"
    key="${key//[[:space:]]/}"
    [[ "$key" =~ ^[A-Z][A-Z0-9_]*$ ]] || continue
    [[ "$KNOWN_KEYS" == *" $key "* ]] || continue
    value="${value#"${value%%[![:space:]]*}"}"
    value="${value%"${value##*[![:space:]]}"}"
    if [[ ${#value} -ge 2 && ( "${value:0:1}" == '"' || "${value:0:1}" == "'" ) && "${value: -1}" == "${value:0:1}" ]]; then
      value="${value:1:${#value}-2}"
    fi
    [[ -n "$value" ]] && printf -v "ENV_${key}" '%s' "$value"
  done < "$file"
}

CONFIG_FILE=""
if [[ -f "$PROJECT_ENV" ]]; then
  CONFIG_FILE="$PROJECT_ENV"
elif [[ -f "$GLOBAL_ENV" ]]; then
  CONFIG_FILE="$GLOBAL_ENV"
fi
if [[ -n "$CONFIG_FILE" ]]; then
  check_perms "$CONFIG_FILE"
  load_env_vars "$CONFIG_FILE"
fi

value_of() {
  local name="ENV_$1"
  local from_file="${!name:-}"
  local from_env="${!1:-}"
  printf '%s' "${from_file:-$from_env}"
}

logged_in() {
  # A saved session from `last30days.py login <platform>` (or --cookie import).
  [[ -f "$COOKIE_DIR/$1_login.json" || ( "$1" != "xiaohongshu" && "$1" != "weibo" && -f "$COOKIE_DIR/$1_cookies.json" ) ]]
}

READY=()
MISSING=()

if [[ -n "$(value_of WEIBO_COOKIE)$(value_of WEIBO_ACCESS_TOKEN)" ]] || logged_in weibo; then READY+=("微博"); else MISSING+=("微博"); fi
if [[ -n "$(value_of XIAOHONGSHU_API_BASE)" ]] || logged_in xiaohongshu; then READY+=("小红书"); else MISSING+=("小红书"); fi
if [[ -n "$(value_of ZHIHU_COOKIE)" ]] || logged_in zhihu; then READY+=("知乎"); else MISSING+=("知乎"); fi
if [[ -n "$(value_of TIKHUB_API_KEY)$(value_of DOUYIN_API_KEY)" ]] || logged_in douyin; then READY+=("抖音"); else MISSING+=("抖音"); fi

echo "last30days-cn v4：B站、今日头条、微信公众号、百度与全网热榜（--hot）开箱可用。"
if [[ ${#READY[@]} -gt 0 ]]; then
  echo "  已登录/已配置：${READY[*]}"
fi
if [[ ${#MISSING[@]} -gt 0 ]]; then
  echo "  未登录：${MISSING[*]}（会改用热榜匹配 + 公开搜索兜底）。一次性修复：python scripts/last30days.py login <平台>，或 --diagnose 查看详情。"
fi
