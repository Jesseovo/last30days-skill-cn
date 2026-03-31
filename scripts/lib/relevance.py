"""Shared token-overlap relevance scoring for search result ranking.

Author: Jesse (https://github.com/ChiTing111)

The score is intentionally query-centric:
- exact phrase matches should score very high
- partial matches should pay a meaningful penalty
- matches on generic words alone ("odds", "review") should not pass as relevant
"""

import re
from typing import List, Optional, Set

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def _has_cjk(s: str) -> bool:
    return bool(_CJK_RE.search(s))


# Stopwords for relevance computation (common English + Chinese)
STOPWORDS = frozenset({
    'the', 'a', 'an', 'to', 'for', 'how', 'is', 'in', 'of', 'on',
    'and', 'with', 'from', 'by', 'at', 'this', 'that', 'it', 'my',
    'your', 'i', 'me', 'we', 'you', 'what', 'are', 'do', 'can',
    'its', 'be', 'or', 'not', 'no', 'so', 'if', 'but', 'about',
    'all', 'just', 'get', 'has', 'have', 'was', 'will',
    '的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '上', '也', '到',
    '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这', '他', '她', '很', '么',
})

# Synonym groups for relevance scoring (bidirectional expansion)
SYNONYMS = {
    'hip': {'rap', 'hiphop'},
    'hop': {'rap', 'hiphop'},
    'rap': {'hip', 'hop', 'hiphop'},
    'hiphop': {'rap', 'hip', 'hop'},
    'js': {'javascript'},
    'javascript': {'js'},
    'ts': {'typescript'},
    'typescript': {'ts'},
    'ai': {'artificial', 'intelligence', '人工智能', '机器学习', '深度学习'},
    'artificial': {'ai', 'intelligence'},
    'intelligence': {'ai', 'artificial'},
    'ml': {'machine', 'learning'},
    'machine': {'ml', 'learning'},
    'learning': {'ml', 'machine'},
    'react': {'reactjs'},
    'reactjs': {'react'},
    'svelte': {'sveltejs'},
    'sveltejs': {'svelte'},
    'vue': {'vuejs'},
    'vuejs': {'vue'},
    '人工智能': {'ai', '机器学习', '深度学习'},
    '机器学习': {'ai', '人工智能', '深度学习'},
    '深度学习': {'ai', '人工智能', '机器学习'},
}

# Generic query words that should not carry relevance on their own.
LOW_SIGNAL_QUERY_TOKENS = frozenset({
    'advice', 'animation', 'animations', 'best', 'chance', 'chances',
    'code', 'compare', 'comparison', 'differences', 'explain', 'guide',
    'guides', 'how', 'latest', 'news', 'odds', 'opinion', 'opinions',
    'prediction', 'predictions', 'probability', 'probabilities', 'prompt',
    'prompting', 'prompts', 'rate', 'review', 'reviews', 'thoughts',
    'tip', 'tips', 'tutorial', 'tutorials', 'update', 'updates', 'use',
    'using', 'versus', 'vs', 'worth',
    '建议', '推荐', '教程', '评测', '对比', '最新', '消息', '更新', '分享', '经验',
})


def _keep_token(w: str) -> bool:
    if not w or w in STOPWORDS:
        return False
    if _has_cjk(w):
        return True
    return len(w) > 1


def _expand_synonyms(tokens: Set[str]) -> Set[str]:
    expanded = set(tokens)
    for t in tokens:
        if t in SYNONYMS:
            expanded.update(SYNONYMS[t])
    return expanded


def tokenize(text: str) -> Set[str]:
    """Lowercase, strip punctuation, remove stopwords, drop low-value English tokens.

    Uses jieba when the text contains Han characters; otherwise whitespace split.
    Expands tokens with synonyms for better cross-domain matching.
    """
    lower = text.lower()
    has_chinese = bool(re.search(r'[\u4e00-\u9fff]', lower))

    if has_chinese:
        try:
            import jieba
            words = list(jieba.cut(lower))
            tokens = {w for w in words if _keep_token(w)}
            return _expand_synonyms(tokens)
        except ImportError:
            tokens = set()
            for w in re.sub(r'[^\w\s]', ' ', lower).split():
                if re.search(r'[\u4e00-\u9fff]', w):
                    for ch in w:
                        if _keep_token(ch):
                            tokens.add(ch)
                elif _keep_token(w):
                    tokens.add(w)
            return _expand_synonyms(tokens)

    words = re.sub(r'[^\w\s]', ' ', lower).split()
    tokens = {w for w in words if _keep_token(w)}
    return _expand_synonyms(tokens)


def _normalize_phrase(text: str) -> str:
    """Normalize text for phrase containment checks."""
    return ' '.join(re.sub(r'[^\w\s]', ' ', text.lower()).split())


def token_overlap_relevance(
    query: str,
    text: str,
    hashtags: Optional[List[str]] = None,
) -> float:
    """Compute a query-centric relevance score between 0.0 and 1.0.

    The score combines:
    - query coverage
    - informative-token coverage
    - a small precision term to penalize extra noise
    - an exact phrase bonus

    Generic tokens alone are capped below the post-retrieval 0.3 threshold.

    Args:
        query: Search query
        text: Content text to match against
        hashtags: Optional list of hashtags (抖音/小红书). Concatenated
            hashtags are split to match query tokens (e.g. "claudecode" matches "claude").

    Returns:
        Float between 0.0 and 1.0 (0.5 for empty queries)
    """
    q_tokens = tokenize(query)

    combined = text
    if hashtags:
        combined = f"{text} {' '.join(hashtags)}"
    t_tokens = tokenize(combined)

    if hashtags:
        for tag in hashtags:
            tag_lower = tag.lower()
            for qt in q_tokens:
                if qt in tag_lower and qt != tag_lower:
                    t_tokens.add(qt)

    if not q_tokens:
        return 0.5

    overlap_tokens = q_tokens & t_tokens
    overlap = len(overlap_tokens)
    if overlap == 0:
        return 0.0

    informative_q_tokens = {t for t in q_tokens if t not in LOW_SIGNAL_QUERY_TOKENS}
    if not informative_q_tokens:
        informative_q_tokens = q_tokens

    coverage = overlap / len(q_tokens)
    informative_overlap = len(informative_q_tokens & t_tokens) / len(informative_q_tokens)
    precision_denominator = min(len(t_tokens), len(q_tokens) + 4) or 1
    precision = overlap / precision_denominator

    phrase_bonus = 0.0
    normalized_query = _normalize_phrase(query)
    normalized_text = _normalize_phrase(combined)
    if normalized_query and normalized_query in normalized_text:
        phrase_bonus = 0.12 if len(normalized_query.split()) > 1 else 0.16

    base = (
        0.55 * (coverage ** 1.35) +
        0.25 * informative_overlap +
        0.20 * precision
    )

    if informative_q_tokens and not (informative_q_tokens & t_tokens):
        return round(min(0.24, base), 2)

    return round(min(1.0, base + phrase_bonus), 2)
