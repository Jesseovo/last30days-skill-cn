"""last30days-cn 终端界面工具。

Author: Jesse (https://github.com/ChiTing111)
"""

import sys
import time
import threading
import random
from typing import Optional

IS_TTY = sys.stderr.isatty()


class Colors:
    PURPLE = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RESET = '\033[0m'


BANNER = f"""{Colors.PURPLE}{Colors.BOLD}
  ██╗      █████╗ ███████╗████████╗██████╗  ██████╗ ██████╗  █████╗ ██╗   ██╗███████╗
  ██║     ██╔══██╗██╔════╝╚══██╔══╝╚════██╗██╔═████╗██╔══██╗██╔══██╗╚██╗ ██╔╝██╔════╝
  ██║     ███████║███████╗   ██║    █████╔╝██║██╔██║██║  ██║███████║ ╚████╔╝ ███████╗
  ██║     ██╔══██║╚════██║   ██║    ╚═══██╗████╔╝██║██║  ██║██╔══██║  ╚██╔╝  ╚════██║
  ███████╗██║  ██║███████║   ██║   ██████╔╝╚██████╔╝██████╔╝██║  ██║   ██║   ███████║
  ╚══════╝╚═╝  ╚═╝╚══════╝   ╚═╝   ╚═════╝  ╚═════╝ ╚═════╝ ╚═╝  ╚═╝   ╚═╝   ╚══════╝
{Colors.RESET}{Colors.DIM}  30 天的研究，30 秒的结果。{Colors.RESET}
"""

MINI_BANNER = f"""{Colors.PURPLE}{Colors.BOLD}/last30days-cn{Colors.RESET} {Colors.DIM}· 正在搜索...{Colors.RESET}"""

WEIBO_MESSAGES = [
    "正在检索微博话题与博文…",
    "翻阅微博实时讨论…",
    "抓取微博热门转发…",
    "扫描微博相关关键词…",
    "汇总微博上的公众声音…",
    "深挖微博评论线索…",
]

XIAOHONGSHU_MESSAGES = [
    "正在搜索小红书笔记…",
    "浏览小红书种草与测评…",
    "抓取小红书热门笔记…",
    "发现小红书上的真实体验…",
    "整理小红书标签内容…",
]

BILIBILI_MESSAGES = [
    "正在搜索 B 站视频与稿件…",
    "翻阅 B 站相关分区…",
    "抓取 B 站弹幕与简介线索…",
    "发现 B 站 UP 主观点…",
    "汇总 B 站近期投稿…",
]

ZHIHU_MESSAGES = [
    "正在搜索知乎问答…",
    "阅读知乎高赞回答…",
    "梳理知乎话题讨论…",
    "发现知乎专业见解…",
    "汇总知乎相关问题…",
]

DOUYIN_MESSAGES = [
    "正在检索抖音短视频…",
    "发现抖音热门话题…",
    "抓取抖音相关视频线索…",
    "浏览抖音创作者动态…",
]

WECHAT_MESSAGES = [
    "正在检索微信公众号文章…",
    "汇总公众号历史推文…",
    "发现公众号深度长文…",
    "抓取公众号标题与摘要…",
]

BAIDU_MESSAGES = [
    "正在通过百度搜索网页…",
    "检索百度新闻与资讯…",
    "汇总百度搜索结果摘要…",
    "发现百度上的相关站点…",
]

TOUTIAO_MESSAGES = [
    "正在搜索今日头条资讯…",
    "翻阅头条热点与稿件…",
    "汇总今日头条相关报道…",
    "发现头条号创作者内容…",
]

PROCESSING_MESSAGES = [
    "正在清洗与去重数据…",
    "打分排序中…",
    "提取模式与要点…",
    "整理研究结果…",
    "合并多源线索…",
]

WEB_ONLY_MESSAGES = [
    "正在搜索开放网页…",
    "检索博客与文档…",
    "浏览新闻站点…",
    "发现教程与解读…",
]


def _build_nux_message(diag: dict = None) -> str:
    if diag:
        def _on(k: str) -> str:
            return "✓" if diag.get(k) else "✗"

        status_line = (
            f"微博 {_on('weibo')}，小红书 {_on('xiaohongshu')}，B站 {_on('bilibili')}，"
            f"知乎 {_on('zhihu')}，抖音 {_on('douyin')}，微信公众号 {_on('wechat')}，"
            f"百度搜索 {_on('baidu')}，今日头条 {_on('toutiao')}"
        )
    else:
        status_line = "百度搜索 ✓，今日头条 ✓，其余信源 ✗"

    return f"""
已为你完成检索，当前可用信源如下：

{status_line}

配置 API 密钥或完成向导后可解锁更多平台；随时问我如何设置。信源越多，综述越全；默认也可用。

示例用法：
- 「last30 大家在聊 Figma 什么」
- 「last30 每周帮我盯竞品动态」
- 「last30 每 30 天汇总一次 AI 视频工具」
- 「last30 关于 AI 视频你找到了什么」

以「last30」开头，像平常对话一样提问即可。
"""


PROMO_SINGLE_KEY = {
    "weibo": "\n💡 配置微博相关 API 或环境变量即可解锁微博信源，需要时问我具体步骤。\n",
    "xiaohongshu": "\n💡 配置小红书数据接口密钥即可解锁小红书笔记，需要时问我如何填写。\n",
    "bilibili": "\n💡 配置 B 站数据接口即可解锁视频与稿件检索，需要时问我。\n",
    "zhihu": "\n💡 配置知乎检索或 API 凭证即可解锁问答信源，需要时问我。\n",
    "douyin": "\n💡 配置抖音相关 API 或爬虫凭证即可解锁短视频线索，需要时问我。\n",
    "wechat": "\n💡 配置微信公众号文章抓取或第三方密钥即可解锁公号内容，需要时问我。\n",
    "baidu": "\n💡 配置百度搜索或网页检索后端密钥可提升网页覆盖，需要时问我。\n",
    "toutiao": "\n💡 配置今日头条数据接口可解锁更多资讯源，需要时问我。\n",
}

SPINNER_FRAMES = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
DOTS_FRAMES = ['   ', '.  ', '.. ', '...']


class Spinner:
    """长时间操作的旋转指示。"""

    def __init__(self, message: str = "处理中", color: str = Colors.CYAN, quiet: bool = False):
        self.message = message
        self.color = color
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.frame_idx = 0
        self.shown_static = False
        self.quiet = quiet

    def _spin(self):
        while self.running:
            frame = SPINNER_FRAMES[self.frame_idx % len(SPINNER_FRAMES)]
            sys.stderr.write(f"\r{self.color}{frame}{Colors.RESET} {self.message}  ")
            sys.stderr.flush()
            self.frame_idx += 1
            time.sleep(0.08)

    def start(self):
        self.running = True
        if IS_TTY:
            self.thread = threading.Thread(target=self._spin, daemon=True)
            self.thread.start()
        else:
            if not self.shown_static and not self.quiet:
                sys.stderr.write(f"⏳ {self.message}\n")
                sys.stderr.flush()
                self.shown_static = True

    def update(self, message: str):
        self.message = message
        if not IS_TTY and not self.shown_static:
            sys.stderr.write(f"⏳ {message}\n")
            sys.stderr.flush()

    def stop(self, final_message: str = ""):
        self.running = False
        if self.thread:
            self.thread.join(timeout=0.2)
        if IS_TTY:
            sys.stderr.write("\r" + " " * 80 + "\r")
        if final_message:
            sys.stderr.write(f"✓ {final_message}\n")
        sys.stderr.flush()


class ProgressDisplay:
    """研究各阶段进度展示。"""

    def __init__(self, topic: str, show_banner: bool = True):
        self.topic = topic
        self.spinner: Optional[Spinner] = None
        self.start_time = time.time()

        if show_banner:
            self._show_banner()

    def _show_banner(self):
        if IS_TTY:
            sys.stderr.write(MINI_BANNER + "\n")
            sys.stderr.write(f"{Colors.DIM}主题：{Colors.RESET}{Colors.BOLD}{self.topic}{Colors.RESET}\n\n")
        else:
            sys.stderr.write(f"/last30days-cn · 正在搜索：{self.topic}\n")
        sys.stderr.flush()

    def start_weibo(self):
        msg = random.choice(WEIBO_MESSAGES)
        self.spinner = Spinner(f"{Colors.YELLOW}微博{Colors.RESET} {msg}", Colors.YELLOW)
        self.spinner.start()

    def end_weibo(self, count: int):
        if self.spinner:
            self.spinner.stop(f"{Colors.YELLOW}微博{Colors.RESET} 找到 {count} 条")

    def start_xiaohongshu(self):
        msg = random.choice(XIAOHONGSHU_MESSAGES)
        self.spinner = Spinner(f"{Colors.PURPLE}小红书{Colors.RESET} {msg}", Colors.PURPLE)
        self.spinner.start()

    def end_xiaohongshu(self, count: int):
        if self.spinner:
            self.spinner.stop(f"{Colors.PURPLE}小红书{Colors.RESET} 找到 {count} 条")

    def start_bilibili(self):
        msg = random.choice(BILIBILI_MESSAGES)
        self.spinner = Spinner(f"{Colors.CYAN}B站{Colors.RESET} {msg}", Colors.CYAN)
        self.spinner.start()

    def end_bilibili(self, count: int):
        if self.spinner:
            self.spinner.stop(f"{Colors.CYAN}B站{Colors.RESET} 找到 {count} 条")

    def start_zhihu(self):
        msg = random.choice(ZHIHU_MESSAGES)
        self.spinner = Spinner(f"{Colors.BLUE}知乎{Colors.RESET} {msg}", Colors.BLUE)
        self.spinner.start()

    def end_zhihu(self, count: int):
        if self.spinner:
            self.spinner.stop(f"{Colors.BLUE}知乎{Colors.RESET} 找到 {count} 条")

    def start_douyin(self):
        msg = random.choice(DOUYIN_MESSAGES)
        self.spinner = Spinner(f"{Colors.RED}抖音{Colors.RESET} {msg}", Colors.RED)
        self.spinner.start()

    def end_douyin(self, count: int):
        if self.spinner:
            self.spinner.stop(f"{Colors.RED}抖音{Colors.RESET} 找到 {count} 条")

    def start_wechat(self):
        msg = random.choice(WECHAT_MESSAGES)
        self.spinner = Spinner(f"{Colors.GREEN}微信公众号{Colors.RESET} {msg}", Colors.GREEN)
        self.spinner.start()

    def end_wechat(self, count: int):
        if self.spinner:
            self.spinner.stop(f"{Colors.GREEN}微信公众号{Colors.RESET} 找到 {count} 条")

    def start_baidu(self):
        msg = random.choice(BAIDU_MESSAGES)
        self.spinner = Spinner(f"{Colors.GREEN}百度搜索{Colors.RESET} {msg}", Colors.GREEN)
        self.spinner.start()

    def end_baidu(self, count: int):
        if self.spinner:
            self.spinner.stop(f"{Colors.GREEN}百度搜索{Colors.RESET} 找到 {count} 条")

    def start_toutiao(self):
        msg = random.choice(TOUTIAO_MESSAGES)
        self.spinner = Spinner(f"{Colors.YELLOW}今日头条{Colors.RESET} {msg}", Colors.YELLOW)
        self.spinner.start()

    def end_toutiao(self, count: int):
        if self.spinner:
            self.spinner.stop(f"{Colors.YELLOW}今日头条{Colors.RESET} 找到 {count} 条")

    def start_processing(self):
        msg = random.choice(PROCESSING_MESSAGES)
        self.spinner = Spinner(f"{Colors.PURPLE}处理{Colors.RESET} {msg}", Colors.PURPLE)
        self.spinner.start()

    def end_processing(self):
        if self.spinner:
            self.spinner.stop()

    def show_complete(
        self,
        weibo_count: int,
        xhs_count: int,
        bilibili_count: int,
        zhihu_count: int,
        douyin_count: int,
        wechat_count: int,
        baidu_count: int,
        toutiao_count: int,
    ):
        elapsed = time.time() - self.start_time
        if IS_TTY:
            sys.stderr.write(f"\n{Colors.GREEN}{Colors.BOLD}✓ 检索完成{Colors.RESET} ")
            sys.stderr.write(f"{Colors.DIM}（{elapsed:.1f} 秒）{Colors.RESET}\n")
            sys.stderr.write(f"  {Colors.YELLOW}微博：{Colors.RESET} {weibo_count}  ")
            sys.stderr.write(f"{Colors.PURPLE}小红书：{Colors.RESET} {xhs_count}  ")
            sys.stderr.write(f"{Colors.CYAN}B站：{Colors.RESET} {bilibili_count}  ")
            sys.stderr.write(f"{Colors.BLUE}知乎：{Colors.RESET} {zhihu_count}  ")
            sys.stderr.write(f"{Colors.RED}抖音：{Colors.RESET} {douyin_count}  ")
            sys.stderr.write(f"{Colors.GREEN}微信公众号：{Colors.RESET} {wechat_count}  ")
            sys.stderr.write(f"{Colors.GREEN}百度搜索：{Colors.RESET} {baidu_count}  ")
            sys.stderr.write(f"{Colors.YELLOW}今日头条：{Colors.RESET} {toutiao_count}")
            sys.stderr.write("\n\n")
        else:
            parts = [
                f"微博 {weibo_count}",
                f"小红书 {xhs_count}",
                f"B站 {bilibili_count}",
                f"知乎 {zhihu_count}",
                f"抖音 {douyin_count}",
                f"微信公众号 {wechat_count}",
                f"百度搜索 {baidu_count}",
                f"今日头条 {toutiao_count}",
            ]
            sys.stderr.write(f"✓ 检索完成（{elapsed:.1f} 秒）- {', '.join(parts)}\n")
        sys.stderr.flush()

    def show_cached(self, age_hours: float = None):
        if age_hours is not None:
            age_str = f"（缓存约 {age_hours:.1f} 小时）"
        else:
            age_str = ""
        sys.stderr.write(
            f"{Colors.GREEN}⚡{Colors.RESET} {Colors.DIM}使用缓存结果{age_str}{Colors.RESET}\n\n"
        )
        sys.stderr.flush()

    def show_error(self, message: str):
        sys.stderr.write(f"{Colors.RED}✗ 错误：{Colors.RESET} {message}\n")
        sys.stderr.flush()

    def start_web_only(self):
        msg = random.choice(WEB_ONLY_MESSAGES)
        self.spinner = Spinner(f"{Colors.GREEN}网页{Colors.RESET} {msg}", Colors.GREEN)
        self.spinner.start()

    def end_web_only(self):
        if self.spinner:
            self.spinner.stop(f"{Colors.GREEN}网页{Colors.RESET} 助手将检索开放网页")

    def show_web_only_complete(self):
        elapsed = time.time() - self.start_time
        if IS_TTY:
            sys.stderr.write(f"\n{Colors.GREEN}{Colors.BOLD}✓ 已就绪（网页检索）{Colors.RESET} ")
            sys.stderr.write(f"{Colors.DIM}（{elapsed:.1f} 秒）{Colors.RESET}\n")
            sys.stderr.write(f"  {Colors.GREEN}网页：{Colors.RESET} 将搜索博客、文档与新闻\n\n")
        else:
            sys.stderr.write(f"✓ 已就绪（网页检索）（{elapsed:.1f} 秒）\n")
        sys.stderr.flush()

    def show_promo(self, missing: str = "both", diag: dict = None):
        if missing in ("both", "all"):
            sys.stderr.write(_build_nux_message(diag))
        elif missing in PROMO_SINGLE_KEY:
            sys.stderr.write(PROMO_SINGLE_KEY[missing])
        else:
            sys.stderr.write(
                "\n💡 在 ~/.config/last30days-cn/.env 中配置各平台密钥，可解锁微博、小红书、B站、知乎、抖音、微信公众号等更多信源；需要时问我步骤。\n"
            )
        sys.stderr.flush()


def _build_status_banner(diag: dict) -> list[str]:
    setup_complete = diag.get("setup_complete", False)

    labels = [
        ("weibo", "微博"),
        ("xiaohongshu", "小红书"),
        ("bilibili", "B站"),
        ("zhihu", "知乎"),
        ("douyin", "抖音"),
        ("wechat", "微信公众号"),
        ("baidu", "百度搜索"),
        ("toutiao", "今日头条"),
    ]

    active: list[str] = []
    for key, label in labels:
        if diag.get(key):
            active.append(label)

    BOX_INNER = 53
    PREFIX = "  "

    def _wrap_sources(sources: list[str]) -> list[str]:
        result_lines: list[str] = []
        current = PREFIX
        for s in sources:
            token = f"✅ {s}"
            sep = "  " if current != PREFIX else ""
            if len(current) + len(sep) + len(token) > BOX_INNER:
                result_lines.append(current)
                current = PREFIX + token
            else:
                current += sep + token
        if current.strip():
            result_lines.append(current)
        return result_lines

    source_lines = _wrap_sources(active)

    if not setup_complete:
        title = "/last30days-cn v1.0 — 首次运行"
    else:
        title = "/last30days-cn v1.0 — 信源状态"

    suggestions: list[str] = []
    if not setup_complete:
        suggestions.append("运行 /last30days-cn setup 以配置更多信源")
    elif len(active) < len(labels):
        suggestions.append("⭐ 在 ~/.config/last30days-cn/.env 填写各平台 API，可解锁微博、小红书、B站、知乎、抖音、微信公众号等完整能力")

    content: list[str] = []
    content.append(f" {title}")
    content.append("")
    if source_lines:
        for sl in source_lines:
            content.append(sl)
    else:
        content.append(f"{PREFIX}（当前无已启用的信源，请运行 setup 或检查配置）")

    if suggestions:
        content.append("")
        for sg in suggestions:
            content.append(f"  {sg}")

    content.append("")
    content.append("  配置：~/.config/last30days-cn/.env")

    width = max(len(line) for line in content) + 1
    if width < 53:
        width = 53

    lines: list[str] = []
    lines.append("\u250c" + "\u2500" * width + "\u2510")
    for c in content:
        lines.append("\u2502" + c.ljust(width) + "\u2502")
    lines.append("\u2514" + "\u2500" * width + "\u2518")

    return lines


def _colorize_banner(lines: list[str]) -> list[str]:
    colored: list[str] = []
    for line in lines:
        if line.startswith("\u250c") or line.startswith("\u2514"):
            colored.append(f"{Colors.DIM}{line}{Colors.RESET}")
        elif line.startswith("\u2502"):
            inner = line[1:-1]
            inner_width = len(inner)
            inner = inner.replace("\u2705", f"{Colors.GREEN}\u2705{Colors.RESET}")
            inner = inner.replace("\u2b50", f"{Colors.YELLOW}\u2b50{Colors.RESET}")
            if "/last30days-cn v1.0" in inner:
                stripped = inner.strip()
                inner = f" {Colors.BOLD}{stripped}{Colors.RESET}"
                visible_len = 1 + len(stripped)
                inner = inner + " " * max(0, inner_width - visible_len)
            colored.append(f"{Colors.DIM}\u2502{Colors.RESET}{inner}{Colors.DIM}\u2502{Colors.RESET}")
        else:
            colored.append(line)
    return colored


def show_diagnostic_banner(diag: dict):
    """起飞前展示已启用的中文平台信源（微博、小红书、B站、知乎、抖音、微信公众号、百度搜索、今日头条）。"""
    lines = _build_status_banner(diag)

    if IS_TTY:
        lines = _colorize_banner(lines)

    sys.stderr.write("\n".join(lines) + "\n\n")
    sys.stderr.flush()


def print_phase(phase: str, message: str):
    colors = {
        "weibo": Colors.YELLOW,
        "xiaohongshu": Colors.PURPLE,
        "bilibili": Colors.CYAN,
        "zhihu": Colors.BLUE,
        "douyin": Colors.RED,
        "wechat": Colors.GREEN,
        "baidu": Colors.GREEN,
        "toutiao": Colors.YELLOW,
        "process": Colors.PURPLE,
        "done": Colors.GREEN,
        "error": Colors.RED,
    }
    color = colors.get(phase, Colors.RESET)
    sys.stderr.write(f"{color}▸{Colors.RESET} {message}\n")
    sys.stderr.flush()
