"""Data schemas for last30days skill (Chinese platforms).

Author: Jesse (https://github.com/ChiTing111)
"""

from dataclasses import dataclass, field, fields
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone


def _engagement_from_dict(d: Optional[Dict[str, Any]]) -> Optional["Engagement"]:
    if not d:
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

    def to_dict(self) -> Optional[Dict[str, Any]]:
        d: Dict[str, Any] = {}
        if self.score is not None:
            d['score'] = self.score
        if self.num_comments is not None:
            d['num_comments'] = self.num_comments
        if self.upvote_ratio is not None:
            d['upvote_ratio'] = self.upvote_ratio
        if self.likes is not None:
            d['likes'] = self.likes
        if self.reposts is not None:
            d['reposts'] = self.reposts
        if self.replies is not None:
            d['replies'] = self.replies
        if self.quotes is not None:
            d['quotes'] = self.quotes
        if self.views is not None:
            d['views'] = self.views
        if self.shares is not None:
            d['shares'] = self.shares
        if self.collects is not None:
            d['collects'] = self.collects
        if self.danmaku is not None:
            d['danmaku'] = self.danmaku
        if self.voteups is not None:
            d['voteups'] = self.voteups
        if self.reads is not None:
            d['reads'] = self.reads
        if self.hot_value is not None:
            d['hot_value'] = self.hot_value
        if self.favorites is not None:
            d['favorites'] = self.favorites
        return d if d else None


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
        d: Dict[str, Any] = {
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
        }
        if self.cross_refs:
            d['cross_refs'] = self.cross_refs
        return d


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
        d: Dict[str, Any] = {
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
        }
        if self.cross_refs:
            d['cross_refs'] = self.cross_refs
        return d


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
        d: Dict[str, Any] = {
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
        }
        if self.cross_refs:
            d['cross_refs'] = self.cross_refs
        return d


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
        d: Dict[str, Any] = {
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
        }
        if self.cross_refs:
            d['cross_refs'] = self.cross_refs
        return d


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
        d: Dict[str, Any] = {
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
        }
        if self.cross_refs:
            d['cross_refs'] = self.cross_refs
        return d


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
        d: Dict[str, Any] = {
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
        }
        if self.cross_refs:
            d['cross_refs'] = self.cross_refs
        return d


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
        d: Dict[str, Any] = {
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
        }
        if self.cross_refs:
            d['cross_refs'] = self.cross_refs
        return d


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

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
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
        if self.cross_refs:
            d['cross_refs'] = self.cross_refs
        return d


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
    best_practices: List[str] = field(default_factory=list)
    prompt_pack: List[str] = field(default_factory=list)
    context_snippet_md: str = ""
    weibo_error: Optional[str] = None
    xiaohongshu_error: Optional[str] = None
    bilibili_error: Optional[str] = None
    zhihu_error: Optional[str] = None
    douyin_error: Optional[str] = None
    wechat_error: Optional[str] = None
    baidu_error: Optional[str] = None
    toutiao_error: Optional[str] = None
    from_cache: bool = False
    cache_age_hours: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            'topic': self.topic,
            'range': {
                'from': self.range_from,
                'to': self.range_to,
            },
            'generated_at': self.generated_at,
            'mode': self.mode,
            'weibo': [w.to_dict() for w in self.weibo],
            'xiaohongshu': [x.to_dict() for x in self.xiaohongshu],
            'bilibili': [b.to_dict() for b in self.bilibili],
            'zhihu': [z.to_dict() for z in self.zhihu],
            'douyin': [d_item.to_dict() for d_item in self.douyin],
            'wechat': [wc.to_dict() for wc in self.wechat],
            'baidu': [bd.to_dict() for bd in self.baidu],
            'toutiao': [t.to_dict() for t in self.toutiao],
            'best_practices': self.best_practices,
            'prompt_pack': self.prompt_pack,
            'context_snippet_md': self.context_snippet_md,
        }
        if self.weibo_error:
            d['weibo_error'] = self.weibo_error
        if self.xiaohongshu_error:
            d['xiaohongshu_error'] = self.xiaohongshu_error
        if self.bilibili_error:
            d['bilibili_error'] = self.bilibili_error
        if self.zhihu_error:
            d['zhihu_error'] = self.zhihu_error
        if self.douyin_error:
            d['douyin_error'] = self.douyin_error
        if self.wechat_error:
            d['wechat_error'] = self.wechat_error
        if self.baidu_error:
            d['baidu_error'] = self.baidu_error
        if self.toutiao_error:
            d['toutiao_error'] = self.toutiao_error
        if self.from_cache:
            d['from_cache'] = self.from_cache
        if self.cache_age_hours is not None:
            d['cache_age_hours'] = self.cache_age_hours
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Report":
        """Create Report from serialized dict (handles cache format)."""
        range_data = data.get('range', {})
        range_from = range_data.get('from', data.get('range_from', ''))
        range_to = range_data.get('to', data.get('range_to', ''))

        weibo_items: List[WeiboItem] = []
        for w in data.get('weibo', []):
            subs = SubScores(**w.get('subs', {})) if w.get('subs') else SubScores()
            weibo_items.append(WeiboItem(
                id=w['id'],
                text=w.get('text', ''),
                url=w['url'],
                author_handle=w.get('author_handle', ''),
                author_id=w.get('author_id'),
                date=w.get('date'),
                date_confidence=w.get('date_confidence', 'low'),
                engagement=_engagement_from_dict(w.get('engagement')),
                relevance=w.get('relevance', 0.5),
                why_relevant=w.get('why_relevant', ''),
                subs=subs,
                score=w.get('score', 0),
                cross_refs=w.get('cross_refs', []),
            ))

        xhs_items: List[XiaohongshuItem] = []
        for x in data.get('xiaohongshu', []):
            subs = SubScores(**x.get('subs', {})) if x.get('subs') else SubScores()
            xhs_items.append(XiaohongshuItem(
                id=x['id'],
                title=x.get('title', ''),
                desc=x.get('desc', ''),
                url=x['url'],
                author_name=x.get('author_name', ''),
                author_id=x.get('author_id'),
                date=x.get('date'),
                date_confidence=x.get('date_confidence', 'low'),
                engagement=_engagement_from_dict(x.get('engagement')),
                hashtags=x.get('hashtags', []),
                relevance=x.get('relevance', 0.5),
                why_relevant=x.get('why_relevant', ''),
                subs=subs,
                score=x.get('score', 0),
                cross_refs=x.get('cross_refs', []),
            ))

        bilibili_items: List[BilibiliItem] = []
        for b in data.get('bilibili', []):
            subs = SubScores(**b.get('subs', {})) if b.get('subs') else SubScores()
            bilibili_items.append(BilibiliItem(
                id=b['id'],
                title=b.get('title', ''),
                url=b['url'],
                bvid=b.get('bvid', ''),
                channel_name=b.get('channel_name', ''),
                author_mid=b.get('author_mid'),
                date=b.get('date'),
                date_confidence=b.get('date_confidence', 'high'),
                engagement=_engagement_from_dict(b.get('engagement')),
                description=b.get('description', ''),
                duration=b.get('duration'),
                relevance=b.get('relevance', 0.7),
                why_relevant=b.get('why_relevant', ''),
                subs=subs,
                score=b.get('score', 0),
                cross_refs=b.get('cross_refs', []),
            ))

        zhihu_items: List[ZhihuItem] = []
        for z in data.get('zhihu', []):
            subs = SubScores(**z.get('subs', {})) if z.get('subs') else SubScores()
            zhihu_items.append(ZhihuItem(
                id=z['id'],
                title=z.get('title', ''),
                excerpt=z.get('excerpt', ''),
                url=z['url'],
                author=z.get('author', ''),
                date=z.get('date'),
                date_confidence=z.get('date_confidence', 'high'),
                content_type=z.get('content_type', ''),
                engagement=_engagement_from_dict(z.get('engagement')),
                relevance=z.get('relevance', 0.5),
                why_relevant=z.get('why_relevant', ''),
                subs=subs,
                score=z.get('score', 0),
                cross_refs=z.get('cross_refs', []),
            ))

        douyin_items: List[DouyinItem] = []
        for d_item in data.get('douyin', []):
            subs = SubScores(**d_item.get('subs', {})) if d_item.get('subs') else SubScores()
            douyin_items.append(DouyinItem(
                id=d_item['id'],
                text=d_item.get('text', ''),
                url=d_item['url'],
                author_name=d_item.get('author_name', ''),
                author_id=d_item.get('author_id'),
                date=d_item.get('date'),
                date_confidence=d_item.get('date_confidence', 'high'),
                engagement=_engagement_from_dict(d_item.get('engagement')),
                hashtags=d_item.get('hashtags', []),
                duration=d_item.get('duration'),
                relevance=d_item.get('relevance', 0.7),
                why_relevant=d_item.get('why_relevant', ''),
                subs=subs,
                score=d_item.get('score', 0),
                cross_refs=d_item.get('cross_refs', []),
            ))

        wechat_items: List[WechatItem] = []
        for wc in data.get('wechat', []):
            subs = SubScores(**wc.get('subs', {})) if wc.get('subs') else SubScores()
            wechat_items.append(WechatItem(
                id=wc['id'],
                title=wc.get('title', ''),
                snippet=wc.get('snippet', ''),
                url=wc['url'],
                source_name=wc.get('source_name', ''),
                wechat_id=wc.get('wechat_id'),
                date=wc.get('date'),
                date_confidence=wc.get('date_confidence', 'low'),
                relevance=wc.get('relevance', 0.5),
                why_relevant=wc.get('why_relevant', ''),
                subs=subs,
                score=wc.get('score', 0),
                cross_refs=wc.get('cross_refs', []),
            ))

        baidu_items: List[BaiduItem] = []
        for bd in data.get('baidu', []):
            subs = SubScores(**bd.get('subs', {})) if bd.get('subs') else SubScores()
            baidu_items.append(BaiduItem(
                id=bd['id'],
                title=bd.get('title', ''),
                snippet=bd.get('snippet', ''),
                url=bd['url'],
                source_domain=bd.get('source_domain', ''),
                date=bd.get('date'),
                date_confidence=bd.get('date_confidence', 'low'),
                relevance=bd.get('relevance', 0.5),
                why_relevant=bd.get('why_relevant', ''),
                subs=subs,
                score=bd.get('score', 0),
                cross_refs=bd.get('cross_refs', []),
            ))

        toutiao_items: List[ToutiaoItem] = []
        for t in data.get('toutiao', []):
            subs = SubScores(**t.get('subs', {})) if t.get('subs') else SubScores()
            toutiao_items.append(ToutiaoItem(
                id=t['id'],
                title=t.get('title', ''),
                abstract=t.get('abstract', ''),
                url=t['url'],
                source_name=t.get('source_name', ''),
                date=t.get('date'),
                date_confidence=t.get('date_confidence', 'high'),
                is_hot=t.get('is_hot', False),
                hot_value=t.get('hot_value'),
                engagement=_engagement_from_dict(t.get('engagement')),
                relevance=t.get('relevance', 0.5),
                why_relevant=t.get('why_relevant', ''),
                subs=subs,
                score=t.get('score', 0),
                cross_refs=t.get('cross_refs', []),
            ))

        return cls(
            topic=data['topic'],
            range_from=range_from,
            range_to=range_to,
            generated_at=data['generated_at'],
            mode=data['mode'],
            weibo=weibo_items,
            xiaohongshu=xhs_items,
            bilibili=bilibili_items,
            zhihu=zhihu_items,
            douyin=douyin_items,
            wechat=wechat_items,
            baidu=baidu_items,
            toutiao=toutiao_items,
            best_practices=data.get('best_practices', []),
            prompt_pack=data.get('prompt_pack', []),
            context_snippet_md=data.get('context_snippet_md', ''),
            weibo_error=data.get('weibo_error'),
            xiaohongshu_error=data.get('xiaohongshu_error'),
            bilibili_error=data.get('bilibili_error'),
            zhihu_error=data.get('zhihu_error'),
            douyin_error=data.get('douyin_error'),
            wechat_error=data.get('wechat_error'),
            baidu_error=data.get('baidu_error'),
            toutiao_error=data.get('toutiao_error'),
            from_cache=data.get('from_cache', False),
            cache_age_hours=data.get('cache_age_hours'),
        )


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
