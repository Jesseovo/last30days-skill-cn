"""Popularity-aware scoring for last30days skill (Chinese platforms).

Author: Jesse (https://github.com/ChiTing111)
"""

import math
from typing import List, Optional, Union

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
    """Normalize a list of values to 0-100 scale.

    Args:
        values: Raw values (None values are preserved)
        default: Default value for None entries

    Returns:
        Normalized values
    """
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
            normalized = ((v - min_val) / range_val) * 100
            result.append(normalized)

    return result


def compute_weibo_engagement_raw(engagement: Optional[schema.Engagement]) -> Optional[float]:
    """0.40*log1p(reposts) + 0.35*log1p(comments) + 0.25*log1p(likes)."""
    if engagement is None:
        return None
    if engagement.reposts is None and engagement.num_comments is None and engagement.likes is None:
        return None
    r = log1p_safe(engagement.reposts)
    c = log1p_safe(engagement.num_comments)
    l = log1p_safe(engagement.likes)
    return 0.40 * r + 0.35 * c + 0.25 * l


def compute_xiaohongshu_engagement_raw(engagement: Optional[schema.Engagement]) -> Optional[float]:
    """0.35*log1p(likes) + 0.30*log1p(collects) + 0.25*log1p(comments) + 0.10*log1p(shares)."""
    if engagement is None:
        return None
    if (
        engagement.likes is None
        and engagement.collects is None
        and engagement.num_comments is None
        and engagement.shares is None
    ):
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
    if engagement is None:
        return None
    if (
        engagement.views is None
        and engagement.danmaku is None
        and engagement.num_comments is None
        and engagement.likes is None
        and engagement.favorites is None
    ):
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
    if engagement is None:
        return None
    if engagement.voteups is None and engagement.num_comments is None and engagement.collects is None:
        return None
    return (
        0.45 * log1p_safe(engagement.voteups)
        + 0.35 * log1p_safe(engagement.num_comments)
        + 0.20 * log1p_safe(engagement.collects)
    )


def compute_douyin_engagement_raw(engagement: Optional[schema.Engagement]) -> Optional[float]:
    """0.35*log1p(likes) + 0.30*log1p(comments) + 0.20*log1p(shares) + 0.15*log1p(views/1000)."""
    if engagement is None:
        return None
    if (
        engagement.likes is None
        and engagement.num_comments is None
        and engagement.shares is None
        and engagement.views is None
    ):
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
    if engagement is None:
        return None
    if engagement.num_comments is None and engagement.reads is None and engagement.likes is None:
        return None
    reads_k = (engagement.reads or 0) / 1000.0
    return (
        0.40 * log1p_safe(engagement.num_comments)
        + 0.35 * log1p_safe(reads_k)
        + 0.25 * log1p_safe(engagement.likes)
    )


def _apply_date_confidence_penalty(overall: float, item) -> float:
    if item.date_confidence == "low":
        overall -= 5
    elif item.date_confidence == "med":
        overall -= 2
    return overall


def score_weibo_items(items: List[schema.WeiboItem]) -> List[schema.WeiboItem]:
    if not items:
        return items
    eng_raw = [compute_weibo_engagement_raw(item.engagement) for item in items]
    eng_normalized = normalize_to_100(eng_raw)
    for i, item in enumerate(items):
        rel_score = int(item.relevance * 100)
        rec_score = dates.recency_score(item.date)
        if eng_normalized[i] is not None:
            eng_score = int(eng_normalized[i])
        else:
            eng_score = DEFAULT_ENGAGEMENT
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


def score_xiaohongshu_items(items: List[schema.XiaohongshuItem]) -> List[schema.XiaohongshuItem]:
    if not items:
        return items
    eng_raw = [compute_xiaohongshu_engagement_raw(item.engagement) for item in items]
    eng_normalized = normalize_to_100(eng_raw)
    for i, item in enumerate(items):
        rel_score = int(item.relevance * 100)
        rec_score = dates.recency_score(item.date)
        if eng_normalized[i] is not None:
            eng_score = int(eng_normalized[i])
        else:
            eng_score = DEFAULT_ENGAGEMENT
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


def score_bilibili_items(items: List[schema.BilibiliItem]) -> List[schema.BilibiliItem]:
    if not items:
        return items
    eng_raw = [compute_bilibili_engagement_raw(item.engagement) for item in items]
    eng_normalized = normalize_to_100(eng_raw)
    for i, item in enumerate(items):
        rel_score = int(item.relevance * 100)
        rec_score = dates.recency_score(item.date)
        if eng_normalized[i] is not None:
            eng_score = int(eng_normalized[i])
        else:
            eng_score = DEFAULT_ENGAGEMENT
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


def score_zhihu_items(items: List[schema.ZhihuItem]) -> List[schema.ZhihuItem]:
    if not items:
        return items
    eng_raw = [compute_zhihu_engagement_raw(item.engagement) for item in items]
    eng_normalized = normalize_to_100(eng_raw)
    for i, item in enumerate(items):
        rel_score = int(item.relevance * 100)
        rec_score = dates.recency_score(item.date)
        if eng_normalized[i] is not None:
            eng_score = int(eng_normalized[i])
        else:
            eng_score = DEFAULT_ENGAGEMENT
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


def score_douyin_items(items: List[schema.DouyinItem]) -> List[schema.DouyinItem]:
    if not items:
        return items
    eng_raw = [compute_douyin_engagement_raw(item.engagement) for item in items]
    eng_normalized = normalize_to_100(eng_raw)
    for i, item in enumerate(items):
        rel_score = int(item.relevance * 100)
        rec_score = dates.recency_score(item.date)
        if eng_normalized[i] is not None:
            eng_score = int(eng_normalized[i])
        else:
            eng_score = DEFAULT_ENGAGEMENT
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


def score_toutiao_items(items: List[schema.ToutiaoItem]) -> List[schema.ToutiaoItem]:
    if not items:
        return items
    eng_raw = [compute_toutiao_engagement_raw(item.engagement) for item in items]
    eng_normalized = normalize_to_100(eng_raw)
    for i, item in enumerate(items):
        rel_score = int(item.relevance * 100)
        rec_score = dates.recency_score(item.date)
        if eng_normalized[i] is not None:
            eng_score = int(eng_normalized[i])
        else:
            eng_score = DEFAULT_ENGAGEMENT
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


def score_wechat_items(
    items: List[schema.WechatItem],
    query_type: QueryType = None,
) -> List[schema.WechatItem]:
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


def score_baidu_items(
    items: List[schema.BaiduItem],
    query_type: QueryType = None,
) -> List[schema.BaiduItem]:
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


def sort_items(
    items: List[
        Union[
            schema.WeiboItem,
            schema.XiaohongshuItem,
            schema.BilibiliItem,
            schema.ZhihuItem,
            schema.DouyinItem,
            schema.WechatItem,
            schema.BaiduItem,
            schema.ToutiaoItem,
        ]
    ],
    query_type: QueryType = None,
) -> List:
    """Sort by score (desc), then date, then source tiebreaker."""
    tiebreaker = (
        TIEBREAKER_BY_TYPE.get(query_type, _DEFAULT_TIEBREAKER) if query_type else _DEFAULT_TIEBREAKER
    )

    def sort_key(item):
        score = -item.score
        date = item.date or "0000-00-00"
        date_key = -int(date.replace("-", ""))
        source_name = _ITEM_SOURCE_MAP.get(type(item), "web")
        source_priority = tiebreaker.get(source_name, 99)
        if isinstance(item, schema.WeiboItem):
            text = item.text
        elif isinstance(item, schema.XiaohongshuItem):
            text = f"{item.title} {item.desc}"
        elif isinstance(item, schema.BilibiliItem):
            text = item.title
        elif isinstance(item, schema.ZhihuItem):
            text = item.title
        elif isinstance(item, schema.DouyinItem):
            text = item.text
        elif isinstance(item, schema.WechatItem):
            text = item.title
        elif isinstance(item, schema.BaiduItem):
            text = item.title
        elif isinstance(item, schema.ToutiaoItem):
            text = item.title
        else:
            text = ""
        return (score, date_key, source_priority, text)

    return sorted(items, key=sort_key)


def relevance_filter(items, source_name: str, threshold: float = 0.3):
    """Filter items below relevance threshold with minimum-result guarantee."""
    import sys

    if len(items) <= 3:
        return items
    passed = [i for i in items if getattr(i, "relevance", 0.0) >= threshold]
    if not passed:
        print(
            f"[{source_name} 警告] 全部结果相关性低于 {threshold}，保留前 3 条",
            file=sys.stderr,
        )
        by_rel = sorted(items, key=lambda x: getattr(x, "relevance", 0.0), reverse=True)
        return by_rel[:3]
    return passed
