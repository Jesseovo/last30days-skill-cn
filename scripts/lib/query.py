"""Shared query preprocessing utilities: noise-word stripping, core subject
extraction, and compound term detection. Used by all search modules.

Author: Jesse (https://github.com/ChiTing111)
"""

import re
from typing import FrozenSet, List, Optional

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def _has_cjk(s: str) -> bool:
    return bool(_CJK_RE.search(s))


# Common multi-word prefixes stripped from all queries (identical across modules)
PREFIXES = [
    # English
    'what are the best', 'what is the best', 'what are the latest',
    'what are people saying about', 'what do people think about',
    'how do i use', 'how to use', 'how to',
    'what are', 'what is', 'tips for', 'best practices for',
    # Chinese
    '大家怎么看',
    '如何使用',
    '推荐一下',
    '最好的',
    '最新的',
    '怎么用',
    '什么是',
]

# Multi-word suffixes (used when strip_suffixes=True)
SUFFIXES = [
    'prompting techniques', 'prompting tips',
    'best practices', 'use cases', 'prompt techniques',
    # Chinese
    '最佳实践', '使用案例', '使用教程', '入门指南',
]

# Base noise words shared across most modules
NOISE_WORDS = frozenset({
    # Articles/prepositions/conjunctions
    'a', 'an', 'the', 'is', 'are', 'was', 'were', 'and', 'or',
    'of', 'in', 'on', 'for', 'with', 'about', 'to',
    # Question words
    'how', 'what', 'which', 'who', 'why', 'when', 'where',
    'does', 'should', 'could', 'would',
    # Research/meta descriptors
    'best', 'top', 'good', 'great', 'awesome', 'killer',
    'latest', 'new', 'news', 'update', 'updates',
    'trendiest', 'trending', 'hottest', 'hot', 'popular', 'viral',
    'practices', 'features', 'guide', 'tutorial',
    'recommendations', 'advice', 'review', 'reviews',
    'usecases', 'examples', 'comparison', 'versus', 'vs',
    'plugin', 'plugins', 'skill', 'skills', 'tool', 'tools',
    # Prompting meta words
    'prompt', 'prompts', 'prompting', 'techniques', 'tips',
    'tricks', 'methods', 'strategies', 'approaches',
    # Action words
    'using', 'uses', 'use',
    # Misc filler
    'people', 'saying', 'think', 'said', 'lately',
    # Chinese noise / function words / meta
    '的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '上', '也', '到',
    '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这', '他', '她', '很', '么',
    '什么', '怎么', '如何', '最好', '推荐', '最新', '最近', '那些', '哪些', '为什么',
})


def _tokenize_for_noise(text: str) -> List[str]:
    if _has_cjk(text):
        try:
            import jieba
            return list(jieba.cut(text))
        except ImportError:
            tokens: List[str] = []
            for segment in re.split(r'\s+', text.strip()):
                if not segment:
                    continue
                if _has_cjk(segment):
                    tokens.extend(list(segment))
                else:
                    tokens.extend(segment.split())
            return tokens
    return text.split()


def extract_core_subject(
    topic: str,
    *,
    noise: Optional[FrozenSet[str]] = None,
    max_words: Optional[int] = None,
    strip_suffixes: bool = False,
) -> str:
    """Extract core subject from a verbose search query.

    Strips common question/meta prefixes and noise words to produce a
    compact search-friendly query. Platforms customize via parameters.

    Args:
        topic: Raw user query
        noise: Override noise word set (default: NOISE_WORDS)
        max_words: Cap result to N words (default: no cap)
        strip_suffixes: Also strip trailing multi-word suffixes

    Returns:
        Cleaned query string
    """
    text = topic.strip().lower()
    if not text:
        return text

    # Phase 1: strip one matching prefix (longest first)
    for p in sorted(PREFIXES, key=len, reverse=True):
        if _has_cjk(p):
            if text.startswith(p):
                text = text[len(p):].strip()
                break
        elif text.startswith(p + ' '):
            text = text[len(p):].strip()
            break

    # Phase 2: strip one matching suffix (opt-in)
    if strip_suffixes:
        for s in sorted(SUFFIXES, key=len, reverse=True):
            if _has_cjk(s):
                if text.endswith(s):
                    text = text[:-len(s)].strip()
                    break
            elif text.endswith(' ' + s):
                text = text[:-len(s)].strip()
                break

    noise_set = noise if noise is not None else NOISE_WORDS
    words = _tokenize_for_noise(text)
    filtered = [w for w in words if w.lower() not in noise_set]

    if max_words is not None and filtered:
        filtered = filtered[:max_words]

    result = ' '.join(filtered) if filtered else text
    if max_words is None:
        return result.rstrip('?!.')
    return (result or topic.lower().strip())


def extract_compound_terms(topic: str) -> List[str]:
    """Detect multi-word terms that should be quoted in search queries.

    Identifies:
    - Hyphenated terms: "multi-agent", "vc-backed"
    - Title-cased multi-word names: "Claude Code", "React Native"
    - Continuous Chinese phrases (2+ Han characters)

    Returns list of terms suitable for quoting (e.g., '"multi-agent"').
    """
    terms: List[str] = []

    # Hyphenated terms
    for match in re.finditer(r'\b\w+-\w+(?:-\w+)*\b', topic):
        terms.append(match.group())

    # Title-cased sequences (2+ capitalized words in a row)
    for match in re.finditer(r'(?:[A-Z][a-z]+\s+){1,}[A-Z][a-z]+', topic):
        terms.append(match.group())

    # Chinese compound spans (greedy runs of Han characters)
    for match in re.finditer(r'[\u4e00-\u9fff]{2,}', topic):
        terms.append(match.group())

    return terms
