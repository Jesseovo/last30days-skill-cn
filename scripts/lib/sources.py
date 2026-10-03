"""Declarative source registry for last30days-cn.

Author: Jesse (https://github.com/Jesseovo)

v4: every source (8 Chinese platforms + opt-in overseas sources) is described
once here. The orchestrator, renderers, clustering and diagnostics read labels,
ID prefixes and grouping from this table instead of keeping eight hand-written
copies in sync (v3 had several render bugs caused by exactly that drift).
"""

from collections import OrderedDict
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Set, Tuple


@dataclass(frozen=True)
class SourceSpec:
    id: str
    label: str
    section: str
    code: str
    prefix: str
    group: str = "cn"
    aliases: Tuple[str, ...] = ()
    default_enabled: bool = True
    description: str = ""


_SPECS: Tuple[SourceSpec, ...] = (
    SourceSpec("weibo", "微博", "微博动态", "WEIBO", "WB", aliases=("wb",),
               description="微博搜索/热搜（搜索需登录态）"),
    SourceSpec("xiaohongshu", "小红书", "小红书笔记", "XHS", "XHS", aliases=("xhs", "rednote", "red"),
               description="小红书笔记（MCP / 登录态浏览器 / 公开搜索）"),
    SourceSpec("bilibili", "B站", "B站视频", "BILI", "BL", aliases=("bili", "b站", "bstation"),
               description="B站视频（WBI 签名搜索，时间窗过滤）"),
    SourceSpec("zhihu", "知乎", "知乎问答", "ZHIHU", "ZH", aliases=("zh",),
               description="知乎问答/专栏（Cookie / 登录态浏览器 / 公开搜索）"),
    SourceSpec("douyin", "抖音", "抖音视频", "DOUYIN", "DY", aliases=("dy",),
               description="抖音视频（TikHub / 登录态浏览器 / 热榜 / 公开搜索）"),
    SourceSpec("wechat", "微信公众号", "微信公众号文章", "WECHAT", "WX", aliases=("weixin", "wx", "mp"),
               description="微信公众号文章（搜狗微信 / API）"),
    SourceSpec("baidu", "百度", "百度搜索结果", "BAIDU", "BD", aliases=("bd",),
               description="百度网页（千帆 API / 网页 / 多引擎兜底）"),
    SourceSpec("toutiao", "今日头条", "今日头条资讯", "TOUTIAO", "TT", aliases=("tt",),
               description="今日头条资讯搜索 + 热榜"),
    # Opt-in overseas sources (issue #9). Off by default; enable with
    # --search hackernews,github / --global / INCLUDE_SOURCES=global.
    SourceSpec("hackernews", "Hacker News", "Hacker News 讨论", "HN", "HN", group="global",
               aliases=("hn",), default_enabled=False, description="Hacker News（Algolia API，免 Key）"),
    SourceSpec("github", "GitHub", "GitHub 仓库与讨论", "GITHUB", "GH", group="global",
               aliases=("gh",), default_enabled=False, description="GitHub 仓库/Issue（可选 GITHUB_TOKEN）"),
    SourceSpec("reddit", "Reddit", "Reddit 讨论", "REDDIT", "RD", group="global",
               aliases=("rd",), default_enabled=False, description="Reddit 公开 JSON（数据中心 IP 常被 403）"),
    SourceSpec("upstream", "海外平台", "海外平台（上游 last30days 引擎）", "GLOBAL", "UP", group="global",
               aliases=("last30days", "x", "twitter", "youtube", "tiktok", "instagram"),
               default_enabled=False,
               description="桥接已安装的 mvanhorn/last30days（X/YouTube/TikTok 等）"),
)

SOURCES: "OrderedDict[str, SourceSpec]" = OrderedDict((spec.id, spec) for spec in _SPECS)
CN_SOURCE_IDS: Tuple[str, ...] = tuple(s.id for s in _SPECS if s.group == "cn")
GLOBAL_SOURCE_IDS: Tuple[str, ...] = tuple(s.id for s in _SPECS if s.group == "global")
# Native overseas sources that need no extra install (the "global" group token).
NATIVE_GLOBAL_IDS: Tuple[str, ...] = ("hackernews", "github", "reddit")

GROUP_TOKENS: Dict[str, Tuple[str, ...]] = {
    "cn": CN_SOURCE_IDS,
    "china": CN_SOURCE_IDS,
    "global": NATIVE_GLOBAL_IDS,
    "intl": NATIVE_GLOBAL_IDS,
    "all": CN_SOURCE_IDS + NATIVE_GLOBAL_IDS,
}

_ALIASES: Dict[str, str] = {}
for _spec in _SPECS:
    _ALIASES[_spec.id] = _spec.id
    for _alias in _spec.aliases:
        _ALIASES[_alias.lower()] = _spec.id

# Upstream-only platform names map to the bridge, remembered for the bridge call.
UPSTREAM_PLATFORM_ALIASES = {"x": "x", "twitter": "x", "youtube": "youtube", "tiktok": "tiktok", "instagram": "instagram"}


class UnknownSourceError(ValueError):
    pass


def get(source_id: str) -> SourceSpec:
    return SOURCES[source_id]


def label(source_id: str) -> str:
    spec = SOURCES.get(source_id)
    return spec.label if spec else source_id


def resolve_token(token: str) -> List[str]:
    """Resolve one ``--search`` token (id, alias or group) to source ids."""
    key = (token or "").strip().lower()
    if not key:
        return []
    if key in GROUP_TOKENS:
        return list(GROUP_TOKENS[key])
    if key in _ALIASES:
        return [_ALIASES[key]]
    raise UnknownSourceError(key)


def parse_list(text: str) -> Tuple[Set[str], Set[str]]:
    """Parse a comma-separated source list.

    Returns ``(source_ids, upstream_platforms)`` where ``upstream_platforms``
    remembers tokens such as ``x``/``youtube`` that are served by the bridge.
    Raises UnknownSourceError on the first unknown token.
    """
    ids: Set[str] = set()
    upstream_platforms: Set[str] = set()
    for token in (text or "").split(","):
        key = token.strip().lower()
        if not key:
            continue
        ids.update(resolve_token(key))
        if key in UPSTREAM_PLATFORM_ALIASES:
            upstream_platforms.add(UPSTREAM_PLATFORM_ALIASES[key])
    return ids, upstream_platforms


def valid_tokens() -> List[str]:
    tokens = set(_ALIASES) | set(GROUP_TOKENS)
    return sorted(tokens)


def ordered(ids: Iterable[str]) -> List[str]:
    wanted = set(ids)
    return [sid for sid in SOURCES if sid in wanted]


_PREFIXES = sorted(((s.prefix, s.id) for s in _SPECS), key=lambda pair: -len(pair[0]))


def source_for_item_id(item_id: str) -> Optional[str]:
    """Map an item id such as ``XHS3`` / ``WB12`` / ``HN2`` to its source id."""
    text = str(item_id or "")
    for prefix, sid in _PREFIXES:
        if text.startswith(prefix) and text[len(prefix):].isdigit():
            return sid
    return None


def label_for_item_id(item_id: str) -> Optional[str]:
    sid = source_for_item_id(item_id)
    return label(sid) if sid else None


PLATFORM_LABELS = {
    "hackernews": "Hacker News",
    "github": "GitHub",
    "reddit": "Reddit",
    "x": "X",
    "youtube": "YouTube",
    "tiktok": "TikTok",
    "instagram": "Instagram",
    "polymarket": "Polymarket",
    "bluesky": "Bluesky",
    "threads": "Threads",
    "web": "Web",
}


def platform_label(platform: str) -> str:
    key = (platform or "").lower()
    if key in SOURCES:
        return SOURCES[key].label
    return PLATFORM_LABELS.get(key, platform or "?")
