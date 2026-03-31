"""首次运行配置向导 (last30days-cn)。

Author: Jesse (https://github.com/ChiTing111)

检测首次运行状态，检查中国平台 API 可用性，写入配置文件。
实际向导界面由 SKILL.md 驱动（LLM 展示），本模块提供检测和配置动作。
"""

import logging
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)


def is_first_run(config: Dict[str, Any]) -> bool:
    """如果 SETUP_COMPLETE 未设置则为首次运行。"""
    return not config.get("SETUP_COMPLETE")


def run_auto_setup(config: Dict[str, Any]) -> Dict[str, Any]:
    """执行自动配置检测。

    检查各平台 API Key 是否可用，返回诊断结果。
    """
    from . import env

    results: Dict[str, Any] = {
        "weibo": env.is_weibo_available(config),
        "xiaohongshu": env.is_xiaohongshu_available(config),
        "bilibili": True,
        "zhihu": True,
        "douyin": env.is_douyin_available(config),
        "wechat": env.is_wechat_available(config),
        "baidu_api": env.is_baidu_api_available(config),
        "toutiao": True,
        "env_written": False,
    }

    available_count = sum(1 for k in ["weibo", "xiaohongshu", "bilibili", "zhihu",
                                       "douyin", "wechat", "baidu_api", "toutiao"]
                         if results.get(k))
    results["available_count"] = available_count
    return results


def write_setup_config(env_path, from_browser: str = "auto") -> bool:
    """写入 SETUP_COMPLETE 到 .env 文件。

    如果文件和父目录不存在则创建。不会覆盖已有的配置。
    """
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
                    key = stripped.split("=", 1)[0].strip()
                    existing_keys.add(key)

        lines_to_add = []
        if "SETUP_COMPLETE" not in existing_keys:
            lines_to_add.append("SETUP_COMPLETE=true")

        if not lines_to_add:
            return True

        with open(env_path, "a", encoding="utf-8") as f:
            if existing_content and not existing_content.endswith("\n"):
                f.write("\n")
            f.write("\n".join(lines_to_add) + "\n")

        return True

    except OSError as exc:
        logger.error("写入配置失败 %s: %s", env_path, exc)
        return False


def get_setup_status_text(results: Dict[str, Any]) -> str:
    """返回自动配置检测的中文摘要。"""
    lines = ["配置检测完成！以下是各平台状态：", ""]

    platform_map = {
        "bilibili": "B站",
        "zhihu": "知乎",
        "toutiao": "今日头条",
        "weibo": "微博",
        "xiaohongshu": "小红书",
        "douyin": "抖音",
        "wechat": "微信公众号",
        "baidu_api": "百度搜索（高级）",
    }

    free_platforms = {"bilibili", "zhihu", "toutiao"}

    for key, name in platform_map.items():
        available = results.get(key, False)
        if available:
            extra = "（免费公开接口）" if key in free_platforms else ""
            lines.append(f"  ✅ {name} — 可用{extra}")
        else:
            if key in free_platforms:
                lines.append(f"  ✅ {name} — 可用（免费公开接口）")
            else:
                lines.append(f"  ❌ {name} — 未配置 API Key")

    count = results.get("available_count", 0)
    lines.extend(["", f"共 {count} 个数据源可用。"])

    if count < 8:
        lines.extend([
            "",
            "💡 提示：配置更多 API Key 可解锁更多数据源。",
            f"   配置文件位置：~/.config/last30days-cn/.env",
        ])

    env_written = results.get("env_written", False)
    if env_written:
        lines.extend(["", "配置已保存。后续运行将自动检测。"])

    return "\n".join(lines)
