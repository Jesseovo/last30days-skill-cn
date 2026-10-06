"""Popularity-aware scoring for last30days skill (Chinese platforms + overseas).

Author: Jesse (https://github.com/Jesseovo)

v4: the eight copy-pasted ``score_*_items`` bodies share one implementation
(``score_engagement_items``); public function names are unchanged.
"""

import math
import sys
from typing import Callable, List, Optional, Union

from . import dates, schema
from .query_type import QueryType, WEBSEARCH_PENALTY_BY_TYPE, TIEBREAKER_BY_TYPE

WEIGHT_RELEVANCE = 0.45
WEIGHT_RECENCY = 0.25
WEIGHT_ENGAGEMENT = 0.30

WEBSEARCH_WEIGHT_RELEVANCE = 0.55
WEBSEARCH_WEIGHT_RECENCY = 0.45
WEBSEARCH_SOURCE_PENALTY = 15

WEBSEARCH_VERIFIED_BONUS = 10
WEBSEARCH_NO_DATE_PENALTY = 20

DEFAULT_ENGAGEMENT = 35
UNKNOWN_ENGAGEMENT_PENALTY = 3

# Below this, an item is noise even when the source returned nothing better.
HARD_RELEVANCE_FLOOR = 0.1


def log1p_safe(x: Optional[Union[int, float]]) -> float:
    """Safe log1p that handles None and negative values (int or float)."""
    if x is None:
        return 0.0
    try:
        xf = float(x)
    except (TypeError, ValueError):
        return 0.0
    if xf < 0:
        return 0.0
    return math.log1p(xf)


def normalize_to_100(values: List[float], default: float = 50) -> List[float]:
    """Normalize a list of values to 0-100 scale (None entries preserved)."""
    valid = [v for v in values if v is not None]
    if not valid:
        return [default if v is None else 50 for v in values]

    min_val = min(valid)
    max_val = max(valid)
    range_val = max_val - min_val

    if range_val == 0:
        return [50 if v is None else 50 for v in values]

    result = []
    for v in values:
        if v is None:
            result.append(None)
        else:
            result.append(((v - min_val) / range_val) * 100)
    return result


def _all_none(engagement, names) -> bool:
    return all(getattr(engagement, name, None) is None for name in names)


def compute_weibo_engagement_raw(engagement: Optional[schema.Engagement]) -> Optional[float]:
    """0.40*log1p(reposts) + 0.35*log1p(comments) + 0.25*log1p(likes)."""
    if engagement is None or _all_none(engagement, ("reposts", "num_comments", "likes")):
        return None
    return (
        0.40 * log1p_safe(engagement.reposts)
        + 0.35 * log1p_safe(engagement.num_comments)
        + 0.25 * log1p_safe(engagement.likes)
    )


def compute_xiaohongshu_engagement_raw(engagement: Optional[schema.Engagement]) -> Optional[float]:
    """0.35*log1p(likes) + 0.30*log1p(collects) + 0.25*log1p(comments) + 0.10*log1p(shares)."""
    if engagement is None or _all_none(engagement, ("likes", "collects", "num_comments", "shares")):
        return None
    return (
        0.35 * log1p_safe(engagement.likes)
        + 0.30 * log1p_safe(engagement.collects)
        + 0.25 * log1p_safe(engagement.num_comments)
        + 0.10 * log1p_safe(engagement.shares)
    )


def compute_bilibili_engagement_raw(engagement: Optional[schema.Engagement]) -> Optional[float]:
    """0.30*log1p(views) + 0.25*log1p(danmaku) + 0.20*log1p(comments)
    + 0.15*log1p(likes) + 0.10*log1p(favorites)."""
    if engagement is None or _all_none(engagement, ("views", "danmaku", "num_comments", "likes", "favorites")):
        return None
    return (
        0.30 * log1p_safe(engagement.views)
        + 0.25 * log1p_safe(engagement.danmaku)
        + 0.20 * log1p_safe(engagement.num_comments)
        + 0.15 * log1p_safe(engagement.likes)
        + 0.10 * log1p_safe(engagement.favorites)
    )


def compute_zhihu_engagement_raw(engagement: Optional[schema.Engagement]) -> Optional[float]:
    """0.45*log1p(voteups) + 0.35*log1p(comments) + 0.20*log1p(collects)."""
    if engagement is None or _all_none(engagement, ("voteups", "num_comments", "collects")):
        return None
    return (
        0.45 * log1p_safe(engagement.voteups)
        + 0.35 * log1p_safe(engagement.num_comments)
        + 0.20 * log1p_safe(engagement.collects)
    )


def compute_douyin_engagement_raw(engagement: Optional[schema.Engagement]) -> Optional[float]:
    """0.35*log1p(likes) + 0.30*log1p(comments) + 0.20*log1p(shares) + 0.15*log1p(views/1000)."""
    if engagement is None or _all_none(engagement, ("likes", "num_comments", "shares", "views")):
        return None
    views_k = (engagement.views or 0) / 1000.0
    return (
        0.35 * log1p_safe(engagement.likes)
        + 0.30 * log1p_safe(engagement.num_comments)
        + 0.20 * log1p_safe(engagement.shares)
        + 0.15 * log1p_safe(views_k)
    )


def compute_toutiao_engagement_raw(engagement: Optional[schema.Engagement]) -> Optional[float]:
    """0.40*log1p(comments) + 0.35*log1p(reads/1000) + 0.25*log1p(likes)."""
    if engagement is None or _all_none(engagement, ("num_comments", "reads", "likes")):
        return None
    reads_k = (engagement.reads or 0) / 1000.0
    return (
        0.40 * log1p_safe(engagement.num_comments)
        + 0.35 * log1p_safe(reads_k)
        + 0.25 * log1p_safe(engagement.likes)
    )


def compute_global_engagement_raw(engagement: Optional[schema.Engagement]) -> Optional[float]:
    """Points/upvotes/stars dominate; comments and views add depth."""
    if engagement is None or _all_none(engagement, ("score", "likes", "stars", "num_comments", "views", "reposts")):
        return None
    primary = engagement.score if engagement.score is not None else (
        engagement.stars if engagement.stars is not None else engagement.likes
    )
    return (
        0.45 * log1p_safe(primary)
        + 0.35 * log1p_safe(engagement.num_comments)
        + 0.10 * log1p_safe(engagement.reposts)
        + 0.10 * log1p_safe((engagement.views or 0) / 1000.0)
    )


def _apply_date_confidence_penalty(overall: float, item) -> float:
    if item.date_confidence == "low":
        overall -= 5
    elif item.date_confidence == "med":
        overall -= 2
    return overall


def score_engagement_items(items: List, engagement_fn: Callable) -> List:
    """Shared relevance + recency + engagement scoring."""
    if not items:
        return items
    eng_raw = [engagement_fn(getattr(item, "engagement", None)) for item in items]
    eng_normalized = normalize_to_100(eng_raw)
    for i, item in enumerate(items):
        rel_score = int(item.relevance * 100)
        rec_score = dates.recency_score(item.date)
        eng_score = int(eng_normalized[i]) if eng_normalized[i] is not None else DEFAULT_ENGAGEMENT
        item.subs = schema.SubScores(relevance=rel_score, recency=rec_score, engagement=eng_score)
        overall = (
            WEIGHT_RELEVANCE * rel_score
            + WEIGHT_RECENCY * rec_score
            + WEIGHT_ENGAGEMENT * eng_score
        )
        if eng_raw[i] is None:
            overall -= UNKNOWN_ENGAGEMENT_PENALTY
        overall = _apply_date_confidence_penalty(overall, item)
        item.score = max(0, min(100, int(overall)))
    return items


def score_weibo_items(items: List[schema.WeiboItem]) -> List[schema.WeiboItem]:
    return score_engagement_items(items, compute_weibo_engagement_raw)


def score_xiaohongshu_items(items: List[schema.XiaohongshuItem]) -> List[schema.XiaohongshuItem]:
    return score_engagement_items(items, compute_xiaohongshu_engagement_raw)


def score_bilibili_items(items: List[schema.BilibiliItem]) -> List[schema.BilibiliItem]:
    return score_engagement_items(items, compute_bilibili_engagement_raw)


def score_zhihu_items(items: List[schema.ZhihuItem]) -> List[schema.ZhihuItem]:
    return score_engagement_items(items, compute_zhihu_engagement_raw)


def score_douyin_items(items: List[schema.DouyinItem]) -> List[schema.DouyinItem]:
    return score_engagement_items(items, compute_douyin_engagement_raw)


def score_toutiao_items(items: List[schema.ToutiaoItem]) -> List[schema.ToutiaoItem]:
    return score_engagement_items(items, compute_toutiao_engagement_raw)


def score_global_items(items: List[schema.GlobalItem]) -> List[schema.GlobalItem]:
    return score_engagement_items(items, compute_global_engagement_raw)


def _score_websearch_items(items: List, query_type: QueryType = None) -> List:
    """Relevance + recency only (WebSearch-style); no engagement data."""
    if not items:
        return items
    for item in items:
        rel_score = int(item.relevance * 100)
        rec_score = dates.recency_score(item.date)
        item.subs = schema.SubScores(relevance=rel_score, recency=rec_score, engagement=0)
        overall = WEBSEARCH_WEIGHT_RELEVANCE * rel_score + WEBSEARCH_WEIGHT_RECENCY * rec_score
        penalty = (
            WEBSEARCH_PENALTY_BY_TYPE.get(query_type, WEBSEARCH_SOURCE_PENALTY)
            if query_type
            else WEBSEARCH_SOURCE_PENALTY
        )
        overall -= penalty
        if item.date_confidence == "high":
            overall += WEBSEARCH_VERIFIED_BONUS
        elif item.date_confidence == "low":
            overall -= WEBSEARCH_NO_DATE_PENALTY
        item.score = max(0, min(100, int(overall)))
    return items


def score_wechat_items(items: List[schema.WechatItem], query_type: QueryType = None) -> List[schema.WechatItem]:
    return _score_websearch_items(items, query_type)


def score_baidu_items(items: List[schema.BaiduItem], query_type: QueryType = None) -> List[schema.BaiduItem]:
    return _score_websearch_items(items, query_type)


_ITEM_SOURCE_MAP = {
    schema.WeiboItem: "weibo",
    schema.XiaohongshuItem: "xiaohongshu",
    schema.BilibiliItem: "bilibili",
    schema.ZhihuItem: "zhihu",
    schema.DouyinItem: "douyin",
    schema.WechatItem: "wechat",
    schema.BaiduItem: "baidu",
    schema.ToutiaoItem: "toutiao",
}
_DEFAULT_TIEBREAKER = {
    "weibo": 0,
    "xiaohongshu": 1,
    "bilibili": 2,
    "zhihu": 3,
    "douyin": 4,
    "wechat": 5,
    "baidu": 6,
    "toutiao": 7,
}


def item_author(item) -> str:
    """Return a normalized author/publisher key, or empty string when unknown."""
    for attr in ("author_name", "author_handle", "channel_name", "author", "source_name", "source_domain"):
        value = getattr(item, attr, None)
        if value:
            return str(value).strip().lower()
    return ""


def apply_per_author_cap(items: List, max_per_author: int = 3) -> List:
    """Limit dominance from one author while preserving existing rank order."""
    if max_per_author <= 0:
        return items
    counts = {}
    kept = []
    for item in items:
        author = item_author(item)
        if not author:
            kept.append(item)
            continue
        current = counts.get(author, 0)
        if current < max_per_author:
            kept.append(item)
            counts[author] = current + 1
    return kept


def _item_text(item) -> str:
    if isinstance(item, (schema.WeiboItem, schema.DouyinItem)):
        return item.text
    if isinstance(item, schema.XiaohongshuItem):
        return f"{item.title} {item.desc}"
    return getattr(item, "title", "") or ""


def sort_items(items: List, query_type: QueryType = None) -> List:
    """Sort by score (desc), then date, then source tiebreaker."""
    tiebreaker = (
        TIEBREAKER_BY_TYPE.get(query_type, _DEFAULT_TIEBREAKER) if query_type else _DEFAULT_TIEBREAKER
    )

    def sort_key(item):
        date = item.date or "0000-00-00"
        try:
            date_key = -int(date.replace("-", ""))
        except ValueError:
            date_key = 0
        source_name = _ITEM_SOURCE_MAP.get(type(item), getattr(item, "platform", "web"))
        return (-item.score, date_key, tiebreaker.get(source_name, 99), _item_text(item))

    return sorted(items, key=sort_key)


def relevance_filter(items, source_name: str, threshold: float = 0.3):
    """Filter items below relevance threshold with a small minimum-result guarantee.

    When nothing passes the threshold, keep up to 3 of the best items that are
    still above ``HARD_RELEVANCE_FLOOR`` (pure noise is never kept).
    """
    if len(items) <= 3:
        return items
    passed = [i for i in items if getattr(i, "relevance", 0.0) >= threshold]
    if not passed:
        by_rel = sorted(items, key=lambda x: getattr(x, "relevance", 0.0), reverse=True)
        kept = [i for i in by_rel[:3] if getattr(i, "relevance", 0.0) >= HARD_RELEVANCE_FLOOR]
        print(
            f"[{source_name} 警告] 全部结果相关性低于 {threshold}，保留 {len(kept)} 条弱相关结果",
            file=sys.stderr,
        )
        return kept
    return passed
