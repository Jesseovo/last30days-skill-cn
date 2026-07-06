"""CJK-aware tokenization helpers with optional jieba support.

The skill keeps jieba optional. When jieba is unavailable, Chinese text falls
back to character bigrams for scoring/deduplication, while outgoing search
query cleanup can preserve whole CJK runs via segment_runs().
"""

from __future__ import annotations

import re
from typing import List

_CJK_CHARS = r"㐀-䶿一-鿿豈-﫿぀-ヿ가-힯"
_CJK_RE = re.compile(f"[{_CJK_CHARS}]")
_CJK_RUN_RE = re.compile(f"[{_CJK_CHARS}]+")
_LATIN_RE = re.compile(r"\w+")

CHINESE_STOPWORDS = frozenset({
    "的", "了", "和", "是", "在", "我", "有", "也", "就", "不", "人", "都",
    "一", "一个", "上", "很", "到", "说", "要", "去", "你", "会", "着",
    "没有", "看", "好", "自己", "这", "那", "这个", "那个", "什么", "怎么",
    "为什么", "以及", "或者", "但是", "因为", "所以", "如果", "可以",
    "这样", "那样", "他们", "我们", "你们", "它", "她", "他", "吗", "呢",
    "吧", "啊", "哦", "嗯", "与", "及", "等", "被", "把", "让", "给", "向",
    "还", "再", "又", "从", "对", "为", "以", "之", "其", "中", "最",
    "最新", "最好", "推荐", "教程", "评测", "对比", "消息", "更新", "分享", "经验",
})

try:
    import jieba as _jieba  # type: ignore

    _jieba.setLogLevel(60)
except Exception:
    _jieba = None


def has_cjk(text: str) -> bool:
    """True when text contains any CJK/kana/hangul character."""
    return bool(text) and _CJK_RE.search(text) is not None


def _cjk_tokens(run: str) -> List[str]:
    if _jieba is not None:
        return [w for w in _jieba.cut(run) if w.strip() and _CJK_RE.search(w)]
    if len(run) <= 1:
        return [run] if run else []
    return [run[i:i + 2] for i in range(len(run) - 1)]


def segment(text: str) -> List[str]:
    """Tokenize mixed CJK/Latin text for scoring and deduplication."""
    if not text:
        return []
    text = text.lower()
    if not has_cjk(text):
        return _LATIN_RE.findall(text)

    out: List[str] = []
    pos = 0
    for match in _CJK_RUN_RE.finditer(text):
        if match.start() > pos:
            out.extend(_LATIN_RE.findall(text[pos:match.start()]))
        out.extend(_cjk_tokens(match.group()))
        pos = match.end()
    if pos < len(text):
        out.extend(_LATIN_RE.findall(text[pos:]))
    return out


def segment_runs(text: str) -> List[str]:
    """Tokenize mixed text while preserving whole CJK runs for search queries."""
    if not text:
        return []
    text = text.lower()
    if not has_cjk(text):
        return _LATIN_RE.findall(text)

    out: List[str] = []
    pos = 0
    for match in _CJK_RUN_RE.finditer(text):
        if match.start() > pos:
            out.extend(_LATIN_RE.findall(text[pos:match.start()]))
        out.append(match.group())
        pos = match.end()
    if pos < len(text):
        out.extend(_LATIN_RE.findall(text[pos:]))
    return out
