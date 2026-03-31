"""Near-duplicate detection for last30days skill (Chinese platforms).

Author: Jesse (https://github.com/ChiTing111)
"""

import re
from typing import List, Set, Tuple, Union

from . import schema

STOPWORDS = frozenset({
    "the", "a", "an", "to", "for", "how", "is", "in", "of", "on",
    "and", "with", "from", "by", "at", "this", "that", "it", "my",
    "your", "i", "me", "we", "you", "what", "are", "do", "can",
    "its", "be", "or", "not", "no", "so", "if", "but", "about",
    "all", "just", "get", "has", "have", "was", "will", "show", "hn",
})


def normalize_text(text: str) -> str:
    """Normalize text for comparison.

    - Lowercase
    - Remove punctuation
    - Collapse whitespace
    """
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def get_ngrams(text: str, n: int = 3) -> Set[str]:
    """Get character n-grams from text."""
    text = normalize_text(text)
    if len(text) < n:
        return {text}
    return {text[i : i + n] for i in range(len(text) - n + 1)}


def jaccard_similarity(set1: Set[str], set2: Set[str]) -> float:
    """Compute Jaccard similarity between two sets."""
    if not set1 or not set2:
        return 0.0
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    return intersection / union if union > 0 else 0.0


AnyItem = Union[
    schema.WeiboItem,
    schema.XiaohongshuItem,
    schema.BilibiliItem,
    schema.ZhihuItem,
    schema.DouyinItem,
    schema.WechatItem,
    schema.BaiduItem,
    schema.ToutiaoItem,
]


def get_item_text(item: AnyItem) -> str:
    """Get comparable text from an item."""
    if isinstance(item, schema.WeiboItem):
        return item.text
    if isinstance(item, schema.XiaohongshuItem):
        return f"{item.title} {item.desc}"
    if isinstance(item, schema.BilibiliItem):
        return f"{item.title} {item.channel_name}"
    if isinstance(item, schema.ZhihuItem):
        return f"{item.title} {item.excerpt}"
    if isinstance(item, schema.DouyinItem):
        return f"{item.text} {item.author_name}"
    if isinstance(item, schema.WechatItem):
        return f"{item.title} {item.snippet}"
    if isinstance(item, schema.BaiduItem):
        return f"{item.title} {item.snippet}"
    if isinstance(item, schema.ToutiaoItem):
        return f"{item.title} {item.abstract}"
    return ""


def _get_cross_source_text(item: AnyItem) -> str:
    """Text for cross-source comparison; truncate short-form content."""
    if isinstance(item, schema.WeiboItem):
        return item.text[:100]
    if isinstance(item, schema.DouyinItem):
        return item.text[:100]
    if isinstance(item, schema.XiaohongshuItem):
        combined = f"{item.title} {item.desc}".strip()
        return combined[:100]
    if isinstance(item, schema.ToutiaoItem):
        return item.title
    if isinstance(item, schema.BilibiliItem):
        return item.title
    if isinstance(item, schema.ZhihuItem):
        return item.title
    return get_item_text(item)


def _tokenize_for_xref(text: str) -> Set[str]:
    """Tokenize text for cross-source token Jaccard comparison."""
    words = re.sub(r"[^\w\s]", " ", text.lower()).split()
    return {w for w in words if w not in STOPWORDS and len(w) > 1}


def _token_jaccard(text_a: str, text_b: str) -> float:
    """Token-level Jaccard similarity (word overlap)."""
    tokens_a = _tokenize_for_xref(text_a)
    tokens_b = _tokenize_for_xref(text_b)
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = len(tokens_a & tokens_b)
    union = len(tokens_a | tokens_b)
    return intersection / union if union else 0.0


def _hybrid_similarity(text_a: str, text_b: str) -> float:
    """Hybrid similarity: max of char-trigram Jaccard and token Jaccard."""
    trigram_sim = jaccard_similarity(get_ngrams(text_a), get_ngrams(text_b))
    token_sim = _token_jaccard(text_a, text_b)
    return max(trigram_sim, token_sim)


def find_duplicates(
    items: List[AnyItem],
    threshold: float = 0.7,
) -> List[Tuple[int, int]]:
    """Find near-duplicate pairs in items."""
    duplicates = []
    ngrams = [get_ngrams(get_item_text(item)) for item in items]
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            similarity = jaccard_similarity(ngrams[i], ngrams[j])
            if similarity >= threshold:
                duplicates.append((i, j))
    return duplicates


def dedupe_items(
    items: List[AnyItem],
    threshold: float = 0.7,
) -> List[AnyItem]:
    """Remove near-duplicates, keeping highest-scored item."""
    if len(items) <= 1:
        return items
    dup_pairs = find_duplicates(items, threshold)
    to_remove = set()
    for i, j in dup_pairs:
        if items[i].score >= items[j].score:
            to_remove.add(j)
        else:
            to_remove.add(i)
    return [item for idx, item in enumerate(items) if idx not in to_remove]


def dedupe_weibo(
    items: List[schema.WeiboItem],
    threshold: float = 0.7,
) -> List[schema.WeiboItem]:
    return dedupe_items(items, threshold)


def dedupe_xiaohongshu(
    items: List[schema.XiaohongshuItem],
    threshold: float = 0.7,
) -> List[schema.XiaohongshuItem]:
    return dedupe_items(items, threshold)


def dedupe_bilibili(
    items: List[schema.BilibiliItem],
    threshold: float = 0.7,
) -> List[schema.BilibiliItem]:
    return dedupe_items(items, threshold)


def dedupe_zhihu(
    items: List[schema.ZhihuItem],
    threshold: float = 0.7,
) -> List[schema.ZhihuItem]:
    return dedupe_items(items, threshold)


def dedupe_douyin(
    items: List[schema.DouyinItem],
    threshold: float = 0.7,
) -> List[schema.DouyinItem]:
    return dedupe_items(items, threshold)


def dedupe_wechat(
    items: List[schema.WechatItem],
    threshold: float = 0.7,
) -> List[schema.WechatItem]:
    return dedupe_items(items, threshold)


def dedupe_baidu(
    items: List[schema.BaiduItem],
    threshold: float = 0.7,
) -> List[schema.BaiduItem]:
    return dedupe_items(items, threshold)


def dedupe_toutiao(
    items: List[schema.ToutiaoItem],
    threshold: float = 0.7,
) -> List[schema.ToutiaoItem]:
    return dedupe_items(items, threshold)


def cross_source_link(
    *source_lists: List[AnyItem],
    threshold: float = 0.40,
) -> None:
    """Annotate items with cross-source references (hybrid similarity)."""
    all_items = []
    for source_list in source_lists:
        all_items.extend(source_list)

    if len(all_items) <= 1:
        return

    texts = [_get_cross_source_text(item) for item in all_items]

    for i in range(len(all_items)):
        for j in range(i + 1, len(all_items)):
            if type(all_items[i]) is type(all_items[j]):
                continue
            similarity = _hybrid_similarity(texts[i], texts[j])
            if similarity >= threshold:
                if all_items[j].id not in all_items[i].cross_refs:
                    all_items[i].cross_refs.append(all_items[j].id)
                if all_items[i].id not in all_items[j].cross_refs:
                    all_items[j].cross_refs.append(all_items[i].id)
