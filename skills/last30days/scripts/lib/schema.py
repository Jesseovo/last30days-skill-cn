"""Data schemas for last30days skill (Chinese platforms + opt-in overseas sources).

Author: Jesse (https://github.com/Jesseovo)

v4: adds ``GlobalItem`` (Hacker News / GitHub / Reddit / upstream bridge),
``Engagement.stars``, per-source run status on ``Report`` and a generic
``Report.from_dict`` (the JSON written by ``to_dict`` is unchanged for the
eight Chinese platforms).
"""

from dataclasses import MISSING, dataclass, field, fields
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _engagement_from_dict(d: Optional[Dict[str, Any]]) -> Optional["Engagement"]:
    if not d or not isinstance(d, dict):
        return None
    valid = {f.name for f in fields(Engagement)}
    filtered = {k: v for k, v in d.items() if k in valid}
    return Engagement(**filtered) if filtered else None


@dataclass
class Engagement:
    """Engagement metrics."""
    score: Optional[int] = None
    num_comments: Optional[int] = None
    upvote_ratio: Optional[float] = None
    likes: Optional[int] = None
    reposts: Optional[int] = None
    replies: Optional[int] = None
    quotes: Optional[int] = None
    views: Optional[int] = None
    shares: Optional[int] = None
    collects: Optional[int] = None
    danmaku: Optional[int] = None
    voteups: Optional[int] = None
    reads: Optional[int] = None
    hot_value: Optional[float] = None
    favorites: Optional[int] = None
    stars: Optional[int] = None

    def to_dict(self) -> Optional[Dict[str, Any]]:
        d: Dict[str, Any] = {}
        for f in fields(self):
            value = getattr(self, f.name)
            if value is not None:
                d[f.name] = value
        return d if d else None

    def is_empty(self) -> bool:
        return all(getattr(self, f.name) is None for f in fields(self))


@dataclass
class Comment:
    """评论数据（热评/精选评论）"""
    score: int
    date: Optional[str]
    author: str
    excerpt: str
    url: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            'score': self.score,
            'date': self.date,
            'author': self.author,
            'excerpt': self.excerpt,
            'url': self.url,
        }


@dataclass
class SubScores:
    """Component scores."""
    relevance: int = 0
    recency: int = 0
    engagement: int = 0

    def to_dict(self) -> Dict[str, int]:
        return {
            'relevance': self.relevance,
            'recency': self.recency,
            'engagement': self.engagement,
        }


def _common_tail(item, d: Dict[str, Any]) -> Dict[str, Any]:
    if item.cross_refs:
        d['cross_refs'] = item.cross_refs
    return d


@dataclass
class WeiboItem:
    """Normalized Weibo (微博) item."""
    id: str
    text: str
    url: str
    author_handle: str
    author_id: Optional[str] = None
    date: Optional[str] = None
    date_confidence: str = "low"
    engagement: Optional[Engagement] = None
    relevance: float = 0.5
    why_relevant: str = ""
    subs: SubScores = field(default_factory=SubScores)
    score: int = 0
    cross_refs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return _common_tail(self, {
            'id': self.id,
            'text': self.text,
            'url': self.url,
            'author_handle': self.author_handle,
            'author_id': self.author_id,
            'date': self.date,
            'date_confidence': self.date_confidence,
            'engagement': self.engagement.to_dict() if self.engagement else None,
            'relevance': self.relevance,
            'why_relevant': self.why_relevant,
            'subs': self.subs.to_dict(),
            'score': self.score,
        })


@dataclass
class XiaohongshuItem:
    """Normalized Xiaohongshu (小红书) item."""
    id: str
    title: str
    desc: str
    url: str
    author_name: str
    author_id: Optional[str] = None
    date: Optional[str] = None
    date_confidence: str = "low"
    engagement: Optional[Engagement] = None
    hashtags: List[str] = field(default_factory=list)
    relevance: float = 0.5
    why_relevant: str = ""
    subs: SubScores = field(default_factory=SubScores)
    score: int = 0
    cross_refs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return _common_tail(self, {
            'id': self.id,
            'title': self.title,
            'desc': self.desc,
            'url': self.url,
            'author_name': self.author_name,
            'author_id': self.author_id,
            'date': self.date,
            'date_confidence': self.date_confidence,
            'engagement': self.engagement.to_dict() if self.engagement else None,
            'hashtags': self.hashtags,
            'relevance': self.relevance,
            'why_relevant': self.why_relevant,
            'subs': self.subs.to_dict(),
            'score': self.score,
        })


@dataclass
class BilibiliItem:
    """Normalized Bilibili (哔哩哔哩) item."""
    id: str
    title: str
    url: str
    bvid: str
    channel_name: str
    author_mid: Optional[str] = None
    date: Optional[str] = None
    date_confidence: str = "high"
    engagement: Optional[Engagement] = None
    description: str = ""
    duration: Optional[int] = None
    relevance: float = 0.7
    why_relevant: str = ""
    subs: SubScores = field(default_factory=SubScores)
    score: int = 0
    cross_refs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return _common_tail(self, {
            'id': self.id,
            'title': self.title,
            'url': self.url,
            'bvid': self.bvid,
            'channel_name': self.channel_name,
            'author_mid': self.author_mid,
            'date': self.date,
            'date_confidence': self.date_confidence,
            'engagement': self.engagement.to_dict() if self.engagement else None,
            'description': self.description,
            'duration': self.duration,
            'relevance': self.relevance,
            'why_relevant': self.why_relevant,
            'subs': self.subs.to_dict(),
            'score': self.score,
        })


@dataclass
class ZhihuItem:
    """Normalized Zhihu (知乎) item."""
    id: str
    title: str
    excerpt: str
    url: str
    author: str
    date: Optional[str] = None
    date_confidence: str = "high"
    content_type: str = ""
    engagement: Optional[Engagement] = None
    relevance: float = 0.5
    why_relevant: str = ""
    subs: SubScores = field(default_factory=SubScores)
    score: int = 0
    cross_refs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return _common_tail(self, {
            'id': self.id,
            'title': self.title,
            'excerpt': self.excerpt,
            'url': self.url,
            'author': self.author,
            'date': self.date,
            'date_confidence': self.date_confidence,
            'content_type': self.content_type,
            'engagement': self.engagement.to_dict() if self.engagement else None,
            'relevance': self.relevance,
            'why_relevant': self.why_relevant,
            'subs': self.subs.to_dict(),
            'score': self.score,
        })


@dataclass
class DouyinItem:
    """Normalized Douyin (抖音) item."""
    id: str
    text: str
    url: str
    author_name: str
    author_id: Optional[str] = None
    date: Optional[str] = None
    date_confidence: str = "high"
    engagement: Optional[Engagement] = None
    hashtags: List[str] = field(default_factory=list)
    duration: Optional[int] = None
    relevance: float = 0.7
    why_relevant: str = ""
    subs: SubScores = field(default_factory=SubScores)
    score: int = 0
    cross_refs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return _common_tail(self, {
            'id': self.id,
            'text': self.text,
            'url': self.url,
            'author_name': self.author_name,
            'author_id': self.author_id,
            'date': self.date,
            'date_confidence': self.date_confidence,
            'engagement': self.engagement.to_dict() if self.engagement else None,
            'hashtags': self.hashtags,
            'duration': self.duration,
            'relevance': self.relevance,
            'why_relevant': self.why_relevant,
            'subs': self.subs.to_dict(),
            'score': self.score,
        })


@dataclass
class WechatItem:
    """Normalized WeChat (微信) public account / article search item."""
    id: str
    title: str
    snippet: str
    url: str
    source_name: str
    wechat_id: Optional[str] = None
    date: Optional[str] = None
    date_confidence: str = "low"
    relevance: float = 0.5
    why_relevant: str = ""
    subs: SubScores = field(default_factory=SubScores)
    score: int = 0
    cross_refs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return _common_tail(self, {
            'id': self.id,
            'title': self.title,
            'snippet': self.snippet,
            'url': self.url,
            'source_name': self.source_name,
            'wechat_id': self.wechat_id,
            'date': self.date,
            'date_confidence': self.date_confidence,
            'relevance': self.relevance,
            'why_relevant': self.why_relevant,
            'subs': self.subs.to_dict(),
            'score': self.score,
        })


@dataclass
class BaiduItem:
    """Normalized Baidu (百度) web search item."""
    id: str
    title: str
    snippet: str
    url: str
    source_domain: str
    date: Optional[str] = None
    date_confidence: str = "low"
    relevance: float = 0.5
    why_relevant: str = ""
    subs: SubScores = field(default_factory=SubScores)
    score: int = 0
    cross_refs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return _common_tail(self, {
            'id': self.id,
            'title': self.title,
            'snippet': self.snippet,
            'url': self.url,
            'source_domain': self.source_domain,
            'date': self.date,
            'date_confidence': self.date_confidence,
            'relevance': self.relevance,
            'why_relevant': self.why_relevant,
            'subs': self.subs.to_dict(),
            'score': self.score,
        })


@dataclass
class ToutiaoItem:
    """Normalized Toutiao (头条) item."""
    id: str
    title: str
    abstract: str
    url: str
    source_name: str
    date: Optional[str] = None
    date_confidence: str = "high"
    is_hot: bool = False
    hot_value: Optional[float] = None
    engagement: Optional[Engagement] = None
    relevance: float = 0.5
    why_relevant: str = ""
    subs: SubScores = field(default_factory=SubScores)
    score: int = 0
    cross_refs: List[str] = field(default_factory=list)
    original_url: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = {
            'id': self.id,
            'title': self.title,
            'abstract': self.abstract,
            'url': self.url,
            'source_name': self.source_name,
            'date': self.date,
            'date_confidence': self.date_confidence,
            'is_hot': self.is_hot,
            'hot_value': self.hot_value,
            'engagement': self.engagement.to_dict() if self.engagement else None,
            'relevance': self.relevance,
            'why_relevant': self.why_relevant,
            'subs': self.subs.to_dict(),
            'score': self.score,
        }
        if self.original_url and self.original_url != self.url:
            d['original_url'] = self.original_url
        return _common_tail(self, d)


@dataclass
class GlobalItem:
    """Normalized overseas item (Hacker News / GitHub / Reddit / upstream bridge)."""
    id: str
    platform: str
    title: str
    url: str
    text: str = ""
    author: str = ""
    container: str = ""
    date: Optional[str] = None
    date_confidence: str = "low"
    engagement: Optional[Engagement] = None
    relevance: float = 0.5
    why_relevant: str = ""
    subs: SubScores = field(default_factory=SubScores)
    score: int = 0
    cross_refs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return _common_tail(self, {
            'id': self.id,
            'platform': self.platform,
            'title': self.title,
            'url': self.url,
            'text': self.text,
            'author': self.author,
            'container': self.container,
            'date': self.date,
            'date_confidence': self.date_confidence,
            'engagement': self.engagement.to_dict() if self.engagement else None,
            'relevance': self.relevance,
            'why_relevant': self.why_relevant,
            'subs': self.subs.to_dict(),
            'score': self.score,
        })


# Report attribute name (== source id) -> item class.
ITEM_CLASSES: Dict[str, type] = {
    'weibo': WeiboItem,
    'xiaohongshu': XiaohongshuItem,
    'bilibili': BilibiliItem,
    'zhihu': ZhihuItem,
    'douyin': DouyinItem,
    'wechat': WechatItem,
    'baidu': BaiduItem,
    'toutiao': ToutiaoItem,
    'hackernews': GlobalItem,
    'github': GlobalItem,
    'reddit': GlobalItem,
    'upstream': GlobalItem,
}
CN_REPORT_KEYS = ('weibo', 'xiaohongshu', 'bilibili', 'zhihu', 'douyin', 'wechat', 'baidu', 'toutiao')
GLOBAL_REPORT_KEYS = ('hackernews', 'github', 'reddit', 'upstream')


def item_from_dict(cls: type, data: Dict[str, Any]):
    """Rebuild any item dataclass from its ``to_dict`` output (lenient)."""
    kwargs: Dict[str, Any] = {}
    for f in fields(cls):
        if f.name not in data:
            if f.default is MISSING and f.default_factory is MISSING:  # type: ignore[misc]
                kwargs[f.name] = ""
            continue
        value = data[f.name]
        if f.name == 'engagement':
            value = _engagement_from_dict(value)
        elif f.name == 'subs':
            value = SubScores(**{k: v for k, v in (value or {}).items() if k in ('relevance', 'recency', 'engagement')})
        elif f.name in ('cross_refs', 'hashtags') and value is None:
            value = []
        kwargs[f.name] = value
    return cls(**kwargs)


@dataclass
class Report:
    """Full research report."""
    topic: str
    range_from: str
    range_to: str
    generated_at: str
    mode: str
    weibo: List[WeiboItem] = field(default_factory=list)
    xiaohongshu: List[XiaohongshuItem] = field(default_factory=list)
    bilibili: List[BilibiliItem] = field(default_factory=list)
    zhihu: List[ZhihuItem] = field(default_factory=list)
    douyin: List[DouyinItem] = field(default_factory=list)
    wechat: List[WechatItem] = field(default_factory=list)
    baidu: List[BaiduItem] = field(default_factory=list)
    toutiao: List[ToutiaoItem] = field(default_factory=list)
    hackernews: List[GlobalItem] = field(default_factory=list)
    github: List[GlobalItem] = field(default_factory=list)
    reddit: List[GlobalItem] = field(default_factory=list)
    upstream: List[GlobalItem] = field(default_factory=list)
    best_practices: List[str] = field(default_factory=list)
    prompt_pack: List[str] = field(default_factory=list)
    context_snippet_md: str = ""
    clusters: List[Dict[str, Any]] = field(default_factory=list)
    weibo_error: Optional[str] = None
    xiaohongshu_error: Optional[str] = None
    bilibili_error: Optional[str] = None
    zhihu_error: Optional[str] = None
    douyin_error: Optional[str] = None
    wechat_error: Optional[str] = None
    baidu_error: Optional[str] = None
    toutiao_error: Optional[str] = None
    hackernews_error: Optional[str] = None
    github_error: Optional[str] = None
    reddit_error: Optional[str] = None
    upstream_error: Optional[str] = None
    from_cache: bool = False
    cache_age_hours: Optional[float] = None
    # v4 run metadata
    search_topic: str = ""
    query_type: str = ""
    depth: str = ""
    source_status: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def items(self, source_id: str) -> List[Any]:
        return getattr(self, source_id, None) or []

    def error(self, source_id: str) -> Optional[str]:
        return getattr(self, f"{source_id}_error", None)

    def active_sources(self) -> List[str]:
        """Sources that ran (status recorded) or carry items/errors."""
        out = []
        for key in CN_REPORT_KEYS + GLOBAL_REPORT_KEYS:
            if key in self.source_status or self.items(key) or self.error(key):
                out.append(key)
        return out

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            'topic': self.topic,
            'range': {
                'from': self.range_from,
                'to': self.range_to,
            },
            'generated_at': self.generated_at,
            'mode': self.mode,
        }
        for key in CN_REPORT_KEYS:
            d[key] = [item.to_dict() for item in self.items(key)]
        for key in GLOBAL_REPORT_KEYS:
            if self.items(key) or key in self.source_status or self.error(key):
                d[key] = [item.to_dict() for item in self.items(key)]
        d['best_practices'] = self.best_practices
        d['prompt_pack'] = self.prompt_pack
        d['context_snippet_md'] = self.context_snippet_md
        for key in CN_REPORT_KEYS + GLOBAL_REPORT_KEYS:
            err = self.error(key)
            if err:
                d[f'{key}_error'] = err
        if self.from_cache:
            d['from_cache'] = self.from_cache
        if self.cache_age_hours is not None:
            d['cache_age_hours'] = self.cache_age_hours
        if self.clusters:
            d['clusters'] = self.clusters
        if self.search_topic:
            d['search_topic'] = self.search_topic
        if self.query_type:
            d['query_type'] = self.query_type
        if self.depth:
            d['depth'] = self.depth
        if self.source_status:
            d['source_status'] = self.source_status
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Report":
        """Create Report from serialized dict (handles cache format)."""
        range_data = data.get('range', {}) or {}
        report = cls(
            topic=data.get('topic', ''),
            range_from=range_data.get('from', data.get('range_from', '')),
            range_to=range_data.get('to', data.get('range_to', '')),
            generated_at=data.get('generated_at', ''),
            mode=data.get('mode', 'all'),
            best_practices=data.get('best_practices', []),
            prompt_pack=data.get('prompt_pack', []),
            context_snippet_md=data.get('context_snippet_md', ''),
            from_cache=data.get('from_cache', False),
            cache_age_hours=data.get('cache_age_hours'),
            clusters=data.get('clusters', []),
            search_topic=data.get('search_topic', ''),
            query_type=data.get('query_type', ''),
            depth=data.get('depth', ''),
            source_status=data.get('source_status', {}) or {},
        )
        for key, item_cls in ITEM_CLASSES.items():
            setattr(report, key, [item_from_dict(item_cls, raw) for raw in data.get(key, []) or [] if isinstance(raw, dict)])
            setattr(report, f'{key}_error', data.get(f'{key}_error'))
        return report


def create_report(
    topic: str,
    from_date: str,
    to_date: str,
    mode: str,
) -> Report:
    """Create a new report with metadata."""
    return Report(
        topic=topic,
        range_from=from_date,
        range_to=to_date,
        generated_at=datetime.now(timezone.utc).isoformat(),
        mode=mode,
    )
