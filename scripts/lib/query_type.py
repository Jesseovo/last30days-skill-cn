"""Query type detection for source selection and scoring adjustments.

Author: Jesse (https://github.com/ChiTing111)
"""

import re
from typing import Literal

QueryType = Literal["product", "concept", "opinion", "how_to", "comparison", "breaking_news", "prediction"]

# Pattern-based classification (no LLM, no external deps)
_PRODUCT_PATTERNS = re.compile(
    r"(?:\b(price|pricing|cost|buy|purchase|deal|discount|subscription|plan|tier|free tier|alternative|prompt|prompts|prompting|template|templates)\b|价格|购买|优惠|折扣|订阅|免费|替代|推荐)",
    re.I,
)
_CONCEPT_PATTERNS = re.compile(
    r"(?:\b(what is|what are|explain|definition|how does|how do|overview|introduction|guide to|primer)\b|什么是|解释|概述|介绍|入门|指南)",
    re.I,
)
_OPINION_PATTERNS = re.compile(
    r"(?:\b(worth it|thoughts on|opinion|review|experience with|recommend|should i|pros and cons|good or bad)\b|值得|怎么样|好不好|推荐|评测|体验)",
    re.I,
)
_HOWTO_PATTERNS = re.compile(
    r"(?:\b(how to|tutorial|step by step|setup|install|configure|deploy|migrate|implement|build a|create a|prompting|prompts?|best practices|tips|examples|animation|animations|video workflow|render pipeline)\b|怎么|如何|教程|步骤|安装|配置|部署|搭建)",
    re.I,
)
_COMPARISON_PATTERNS = re.compile(
    r"(?:\b(vs\.?|versus|compared to|comparison|better than|difference between|switch from)\b|对比|比较|好还是|区别|选择)",
    re.I,
)
_BREAKING_PATTERNS = re.compile(
    r"(?:\b(latest|breaking|just announced|launched|released|new|update|news|happened|today|this week)\b|最新|最近|刚刚|发布|上线|更新|消息|今天|本周)",
    re.I,
)
_PREDICTION_PATTERNS = re.compile(
    r"(?:\b(predict|forecast|odds|chance|probability|election|outcome|bet on|market for)\b|预测|趋势|前景|展望|走势)",
    re.I,
)


def detect_query_type(topic: str) -> QueryType:
    """Classify a query into a type using pattern matching.

    Returns the first match in priority order:
    comparison > how_to > product > opinion > prediction > concept > breaking_news.
    """
    if _COMPARISON_PATTERNS.search(topic):
        return "comparison"
    if _HOWTO_PATTERNS.search(topic):
        return "how_to"
    if _PRODUCT_PATTERNS.search(topic):
        return "product"
    if _OPINION_PATTERNS.search(topic):
        return "opinion"
    if _PREDICTION_PATTERNS.search(topic):
        return "prediction"
    if _CONCEPT_PATTERNS.search(topic):
        return "concept"
    if _BREAKING_PATTERNS.search(topic):
        return "breaking_news"

    return "breaking_news"


# Source tiering by query type.
# Tier 1: always run. Tier 2: run if available. Tier 3: opt-in only.
# Chinese platforms: weibo, xiaohongshu, bilibili, zhihu, douyin, wechat, baidu, toutiao.
SOURCE_TIERS = {
    "product": {"tier1": {"xiaohongshu", "weibo", "bilibili"}, "tier2": {"baidu", "douyin"}},
    "concept": {"tier1": {"xiaohongshu", "zhihu", "baidu"}, "tier2": {"bilibili", "weibo"}},
    "opinion": {"tier1": {"xiaohongshu", "weibo"}, "tier2": {"bilibili", "wechat"}},
    "how_to": {"tier1": {"bilibili", "xiaohongshu", "zhihu"}, "tier2": {"baidu", "weibo"}},
    "comparison": {"tier1": {"xiaohongshu", "zhihu", "bilibili"}, "tier2": {"weibo", "baidu"}},
    "breaking_news": {"tier1": {"weibo", "xiaohongshu", "baidu"}, "tier2": {"zhihu", "wechat", "bilibili"}},
    "prediction": {"tier1": {"toutiao", "weibo", "xiaohongshu"}, "tier2": {"baidu", "zhihu", "bilibili"}},
}

# Baidu search / web-style results penalty by query type (same scale as former websearch).
# Points subtracted from score (0–100). 0 = no penalty, 15 = full penalty.
WEBSEARCH_PENALTY_BY_TYPE = {
    "product": 15,
    "concept": 0,
    "opinion": 15,
    "how_to": 5,
    "comparison": 10,
    "breaking_news": 10,
    "prediction": 15,
}

# Tiebreaker priority overrides by query type (lower = higher priority).
TIEBREAKER_BY_TYPE = {
    "product": {
        "xiaohongshu": 0,
        "weibo": 1,
        "bilibili": 2,
        "douyin": 3,
        "wechat": 4,
        "zhihu": 5,
        "baidu": 6,
        "toutiao": 7,
    },
    "concept": {
        "zhihu": 0,
        "xiaohongshu": 1,
        "baidu": 2,
        "bilibili": 3,
        "weibo": 4,
        "douyin": 5,
        "wechat": 6,
        "toutiao": 7,
    },
    "opinion": {
        "xiaohongshu": 0,
        "weibo": 1,
        "wechat": 2,
        "bilibili": 3,
        "zhihu": 4,
        "douyin": 5,
        "baidu": 6,
        "toutiao": 7,
    },
    "how_to": {
        "bilibili": 0,
        "xiaohongshu": 1,
        "zhihu": 2,
        "baidu": 3,
        "weibo": 4,
        "douyin": 5,
        "wechat": 6,
        "toutiao": 7,
    },
    "comparison": {
        "xiaohongshu": 0,
        "zhihu": 1,
        "bilibili": 2,
        "weibo": 3,
        "baidu": 4,
        "douyin": 5,
        "wechat": 6,
        "toutiao": 7,
    },
    "breaking_news": {
        "weibo": 0,
        "xiaohongshu": 1,
        "baidu": 2,
        "zhihu": 3,
        "wechat": 4,
        "douyin": 5,
        "bilibili": 6,
        "toutiao": 7,
    },
    "prediction": {
        "toutiao": 0,
        "weibo": 1,
        "xiaohongshu": 2,
        "baidu": 3,
        "zhihu": 4,
        "wechat": 5,
        "bilibili": 6,
        "douyin": 7,
    },
}


def is_source_enabled(source: str, query_type: QueryType, explicitly_requested: bool = False) -> bool:
    """Check if a source should run for a given query type.

    Tier 1 and Tier 2 sources are enabled. Tier 3 (unlisted) sources only run
    if explicitly requested via --search flag.
    """
    if explicitly_requested:
        return True

    tiers = SOURCE_TIERS.get(query_type, SOURCE_TIERS["breaking_news"])
    return source in tiers["tier1"] or source in tiers["tier2"]
