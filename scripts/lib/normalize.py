"""Normalization of raw API data to canonical schema (Chinese platforms).

Author: Jesse (https://github.com/ChiTing111)
"""

from typing import Any, Dict, List, TypeVar

from . import dates, schema

T = TypeVar(
    "T",
    schema.WeiboItem,
    schema.XiaohongshuItem,
    schema.BilibiliItem,
    schema.ZhihuItem,
    schema.DouyinItem,
    schema.WechatItem,
    schema.BaiduItem,
    schema.ToutiaoItem,
)


def filter_by_date_range(
    items: List[T],
    from_date: str,
    to_date: str,
    require_date: bool = False,
) -> List[T]:
    """Hard filter: Remove items outside the date range."""
    result = []
    for item in items:
        if item.date is None:
            if not require_date:
                result.append(item)
            continue
        if item.date < from_date:
            continue
        if item.date > to_date:
            continue
        result.append(item)
    return result


def normalize_weibo_items(
    items: List[Dict[str, Any]],
    from_date: str,
    to_date: str,
) -> List[schema.WeiboItem]:
    normalized = []
    for item in items:
        engagement = None
        eng_raw = item.get("engagement")
        if isinstance(eng_raw, dict):
            engagement = schema.Engagement(
                reposts=eng_raw.get("reposts"),
                num_comments=eng_raw.get("comments"),
                likes=eng_raw.get("likes"),
            )
        date_str = item.get("date")
        date_confidence = dates.get_date_confidence(date_str, from_date, to_date)
        normalized.append(
            schema.WeiboItem(
                id=item.get("id", ""),
                text=item.get("text", ""),
                url=item.get("url", ""),
                author_handle=item.get("author_handle", ""),
                author_id=item.get("author_id"),
                date=date_str,
                date_confidence=date_confidence,
                engagement=engagement,
                relevance=item.get("relevance", 0.5),
                why_relevant=item.get("why_relevant", ""),
            )
        )
    return normalized


def normalize_xiaohongshu_items(
    items: List[Dict[str, Any]],
    from_date: str,
    to_date: str,
) -> List[schema.XiaohongshuItem]:
    normalized = []
    for item in items:
        engagement = None
        eng_raw = item.get("engagement")
        if isinstance(eng_raw, dict):
            engagement = schema.Engagement(
                likes=eng_raw.get("likes"),
                collects=eng_raw.get("collects"),
                num_comments=eng_raw.get("comments"),
                shares=eng_raw.get("shares"),
            )
        date_str = item.get("date")
        date_confidence = dates.get_date_confidence(date_str, from_date, to_date)
        normalized.append(
            schema.XiaohongshuItem(
                id=item.get("id", ""),
                title=item.get("title", ""),
                desc=item.get("desc", ""),
                url=item.get("url", ""),
                author_name=item.get("author_name", ""),
                author_id=item.get("author_id"),
                date=date_str,
                date_confidence=date_confidence,
                engagement=engagement,
                hashtags=item.get("hashtags", []),
                relevance=item.get("relevance", 0.5),
                why_relevant=item.get("why_relevant", ""),
            )
        )
    return normalized


def normalize_bilibili_items(
    items: List[Dict[str, Any]],
    from_date: str,
    to_date: str,
) -> List[schema.BilibiliItem]:
    normalized = []
    for item in items:
        eng_raw = item.get("engagement") or {}
        engagement = schema.Engagement(
            views=eng_raw.get("views"),
            danmaku=eng_raw.get("danmaku"),
            num_comments=eng_raw.get("comments"),
            likes=eng_raw.get("likes"),
            favorites=eng_raw.get("favorites"),
        )
        date_str = item.get("date")
        date_confidence = dates.get_date_confidence(date_str, from_date, to_date)
        normalized.append(
            schema.BilibiliItem(
                id=item.get("id", ""),
                title=item.get("title", ""),
                url=item.get("url", ""),
                bvid=item.get("bvid", ""),
                channel_name=item.get("channel_name", ""),
                author_mid=item.get("author_mid"),
                date=date_str,
                date_confidence=date_confidence,
                engagement=engagement,
                description=item.get("description", ""),
                duration=item.get("duration"),
                relevance=item.get("relevance", 0.7),
                why_relevant=item.get("why_relevant", ""),
            )
        )
    return normalized


def normalize_zhihu_items(
    items: List[Dict[str, Any]],
    from_date: str,
    to_date: str,
) -> List[schema.ZhihuItem]:
    normalized = []
    for item in items:
        engagement = None
        eng_raw = item.get("engagement")
        if isinstance(eng_raw, dict):
            engagement = schema.Engagement(
                voteups=eng_raw.get("voteups"),
                num_comments=eng_raw.get("comments"),
                collects=eng_raw.get("collects"),
            )
        date_str = item.get("date")
        date_confidence = dates.get_date_confidence(date_str, from_date, to_date)
        normalized.append(
            schema.ZhihuItem(
                id=item.get("id", ""),
                title=item.get("title", ""),
                excerpt=item.get("excerpt", ""),
                url=item.get("url", ""),
                author=item.get("author", ""),
                date=date_str,
                date_confidence=date_confidence,
                content_type=item.get("content_type", ""),
                engagement=engagement,
                relevance=item.get("relevance", 0.5),
                why_relevant=item.get("why_relevant", ""),
            )
        )
    return normalized


def normalize_douyin_items(
    items: List[Dict[str, Any]],
    from_date: str,
    to_date: str,
) -> List[schema.DouyinItem]:
    normalized = []
    for item in items:
        eng_raw = item.get("engagement") or {}
        engagement = schema.Engagement(
            views=eng_raw.get("views"),
            likes=eng_raw.get("likes"),
            num_comments=eng_raw.get("comments"),
            shares=eng_raw.get("shares"),
        )
        date_str = item.get("date")
        date_confidence = dates.get_date_confidence(date_str, from_date, to_date)
        normalized.append(
            schema.DouyinItem(
                id=item.get("id", ""),
                text=item.get("text", ""),
                url=item.get("url", ""),
                author_name=item.get("author_name", ""),
                author_id=item.get("author_id"),
                date=date_str,
                date_confidence=date_confidence,
                engagement=engagement,
                hashtags=item.get("hashtags", []),
                duration=item.get("duration"),
                relevance=item.get("relevance", 0.7),
                why_relevant=item.get("why_relevant", ""),
            )
        )
    return normalized


def normalize_wechat_items(
    items: List[Dict[str, Any]],
    from_date: str,
    to_date: str,
) -> List[schema.WechatItem]:
    normalized = []
    for item in items:
        date_str = item.get("date")
        dc = item.get("date_confidence")
        if dc is None:
            date_confidence = dates.get_date_confidence(date_str, from_date, to_date)
        else:
            date_confidence = dc
        normalized.append(
            schema.WechatItem(
                id=item.get("id", ""),
                title=item.get("title", ""),
                snippet=item.get("snippet", ""),
                url=item.get("url", ""),
                source_name=item.get("source_name", ""),
                wechat_id=item.get("wechat_id"),
                date=date_str,
                date_confidence=date_confidence,
                relevance=item.get("relevance", 0.5),
                why_relevant=item.get("why_relevant", ""),
            )
        )
    return normalized


def normalize_baidu_items(
    items: List[Dict[str, Any]],
    from_date: str,
    to_date: str,
) -> List[schema.BaiduItem]:
    normalized = []
    for item in items:
        date_str = item.get("date")
        dc = item.get("date_confidence")
        if dc is None:
            date_confidence = dates.get_date_confidence(date_str, from_date, to_date)
        else:
            date_confidence = dc
        normalized.append(
            schema.BaiduItem(
                id=item.get("id", ""),
                title=item.get("title", ""),
                snippet=item.get("snippet", ""),
                url=item.get("url", ""),
                source_domain=item.get("source_domain", ""),
                date=date_str,
                date_confidence=date_confidence,
                relevance=item.get("relevance", 0.5),
                why_relevant=item.get("why_relevant", ""),
            )
        )
    return normalized


def normalize_toutiao_items(
    items: List[Dict[str, Any]],
    from_date: str,
    to_date: str,
) -> List[schema.ToutiaoItem]:
    normalized = []
    for item in items:
        engagement = None
        eng_raw = item.get("engagement")
        if isinstance(eng_raw, dict) and eng_raw:
            engagement = schema.Engagement(
                num_comments=eng_raw.get("comments"),
                likes=eng_raw.get("likes"),
                reads=eng_raw.get("reads"),
                hot_value=eng_raw.get("hot_value"),
            )
        date_str = item.get("date")
        date_confidence = dates.get_date_confidence(date_str, from_date, to_date)
        normalized.append(
            schema.ToutiaoItem(
                id=item.get("id", ""),
                title=item.get("title", ""),
                abstract=item.get("abstract", ""),
                url=item.get("url", ""),
                source_name=item.get("source_name", ""),
                date=date_str,
                date_confidence=date_confidence,
                is_hot=bool(item.get("is_hot", False)),
                hot_value=item.get("hot_value"),
                engagement=engagement,
                relevance=item.get("relevance", 0.5),
                why_relevant=item.get("why_relevant", ""),
            )
        )
    return normalized


def items_to_dicts(items: List) -> List[Dict[str, Any]]:
    """Convert schema items to dicts for JSON serialization."""
    return [item.to_dict() for item in items]
