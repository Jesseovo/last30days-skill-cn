"""首次运行配置向导 (last30days-cn)。

Author: Jesse (https://github.com/Jesseovo)

检测各平台当前可用的数据路径，写入 ``SETUP_COMPLETE``，并在配置文件不存在时
生成一份带注释的 .env 模板（所有键均为可选）。
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

ENV_TEMPLATE = """# ============================================
# last30days-cn 配置文件（所有项均为可选）
# 文档: https://github.com/Jesseovo/last30days-skill-cn
# ============================================

# --- 登录态（推荐用 `python scripts/last30days.py login <平台>` 扫码保存，
#     无图形界面时也可把浏览器复制的 Cookie 填在这里）---
# WEIBO_COOKIE=
# ZHIHU_COOKIE=
# BILIBILI_COOKIE=

# --- API Key ---
# TIKHUB_API_KEY=          # 抖音（tikhub.io）
# WECHAT_API_KEY=          # 微信公众号（极速数据 jisuapi）
# BAIDU_API_KEY=           # 百度千帆「AI 搜索」（Bearer Key）
# WEIBO_ACCESS_TOKEN=      # 微博开放平台
# XIAOHONGSHU_API_BASE=    # 自部署 xiaohongshu-mcp，例如 http://127.0.0.1:18060
# GITHUB_TOKEN=            # 海外源 GitHub 提高限额

# --- 运行开关 ---
# LAST30DAYS_DISABLE_BROWSER=1          # 旧电脑：完全不用浏览器
# LAST30DAYS_BROWSER_PATH=/Applications/Google Chrome.app/Contents/MacOS/Google Chrome
# LAST30DAYS_BROWSER_CONCURRENCY=1      # 同时运行的浏览器数量
# INCLUDE_SOURCES=global                # 默认附带 Hacker News/GitHub/Reddit
# EXCLUDE_SOURCES=douyin                # 默认排除某些平台
# LAST30DAYS_HOT_FEEDS=36氪快讯|https://your-rsshub/36kr/newsflashes
"""


def is_first_run(config: Dict[str, Any]) -> bool:
    """如果 SETUP_COMPLETE 未设置则为首次运行。"""
    return not config.get("SETUP_COMPLETE")


def run_auto_setup(config: Dict[str, Any]) -> Dict[str, Any]:
    """执行自动配置检测，返回各平台主路径是否可用。"""
    from . import crawler_bridge, env

    browser = crawler_bridge.is_playwright_available()
    logins = {p: crawler_bridge.has_login(p) for p in crawler_bridge.LOGIN_SPECS}
    results: Dict[str, Any] = {
        "weibo": bool(config.get("WEIBO_ACCESS_TOKEN") or config.get("WEIBO_COOKIE") or (browser and logins["weibo"])),
        "xiaohongshu": bool(env.discover_xiaohongshu_mcp(config) or (browser and logins["xiaohongshu"])),
        "bilibili": True,
        "zhihu": bool(config.get("ZHIHU_COOKIE") or (browser and logins["zhihu"])),
        "douyin": bool(config.get("TIKHUB_API_KEY") or config.get("DOUYIN_API_KEY") or (browser and logins["douyin"])),
        "wechat": True,
        "baidu_api": env.is_baidu_api_available(config),
        "toutiao": True,
        "browser": browser,
        "env_written": False,
    }
    results["available_count"] = sum(
        1 for k in ("weibo", "xiaohongshu", "bilibili", "zhihu", "douyin", "wechat", "baidu_api", "toutiao")
        if results.get(k)
    )
    return results


def write_setup_config(env_path, from_browser: str = "auto") -> bool:
    """写入 SETUP_COMPLETE；文件不存在时先写入带注释的模板。不会覆盖已有配置。"""
    try:
        env_path = Path(env_path)
        env_path.parent.mkdir(parents=True, exist_ok=True)

        existing_keys: set = set()
        existing_content = ""
        if env_path.exists():
            existing_content = env_path.read_text(encoding="utf-8")
            for line in existing_content.splitlines():
                stripped = line.strip()
                if stripped and not stripped.startswith("#") and "=" in stripped:
                    existing_keys.add(stripped.split("=", 1)[0].strip())
        else:
            existing_content = ENV_TEMPLATE
            env_path.write_text(ENV_TEMPLATE, encoding="utf-8")
            if os.name != "nt":
                try:
                    os.chmod(env_path, 0o600)
                except OSError:
                    pass

        if "SETUP_COMPLETE" in existing_keys:
            return True

        with open(env_path, "a", encoding="utf-8") as f:
            if existing_content and not existing_content.endswith("\n"):
                f.write("\n")
            f.write("SETUP_COMPLETE=true\n")
        return True

    except OSError as exc:
        logger.error("写入配置失败 %s: %s", env_path, exc)
        return False


def get_setup_status_text(results: Dict[str, Any]) -> str:
    """返回自动配置检测的中文摘要。"""
    lines = ["配置检测完成！各平台主路径状态：", ""]
    rows = [
        ("bilibili", "B站", "免费公开接口（WBI 签名搜索）", ""),
        ("toutiao", "今日头条", "免费公开接口（资讯搜索 + 热榜）", ""),
        ("wechat", "微信公众号", "搜狗微信公开搜索", ""),
        ("weibo", "微博", "已登录/已配置", "未登录：只用热搜 + 公开搜索兜底 → login weibo"),
        ("xiaohongshu", "小红书", "已登录/MCP 可用", "未登录：只用公开搜索兜底 → login xiaohongshu"),
        ("zhihu", "知乎", "已登录/已配置 Cookie", "未登录：只用热榜 + 公开搜索兜底 → login zhihu"),
        ("douyin", "抖音", "已登录/已配置 TikHub", "未登录：只用热榜 + 公开搜索兜底 → login douyin"),
        ("baidu_api", "百度（千帆 API）", "已配置 BAIDU_API_KEY", "未配置：使用网页搜索 + 多引擎兜底"),
    ]
    for key, name, ok_text, warn_text in rows:
        if results.get(key):
            lines.append(f"  ✅ {name} — {ok_text}")
        else:
            lines.append(f"  ⚠️ {name} — {warn_text}")

    lines.extend(["", f"主路径可用：{results.get('available_count', 0)}/8。"])
    if not results.get("browser"):
        lines.extend([
            "",
            "💡 浏览器模式未启用（登录态平台需要）。安装：",
            "   python -m pip install playwright && python -m playwright install chromium",
            "   旧电脑可设置 LAST30DAYS_BROWSER_PATH 使用系统 Chrome，或保持无浏览器模式。",
        ])
    lines.extend(["", "配置文件：~/.config/last30days-cn/.env（运行 --diagnose 查看完整诊断）"])
    if results.get("env_written"):
        lines.extend(["", "配置已保存。"])
    return "\n".join(lines)
