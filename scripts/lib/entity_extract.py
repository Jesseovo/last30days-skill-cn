"""Entity extraction from Phase 1 search results for supplemental searches.

Author: Jesse (https://github.com/ChiTing111)
"""

import re
from collections import Counter
from typing import Any, Dict, List, Optional

# Accounts that appear too frequently to be useful for targeted search.
GENERIC_HANDLES = frozenset(
    {
        "人民日报",
        "央视新闻",
        "新华社",
        "人民网",
        "环球网",
        "中国日报",
        "光明日报",
        "经济日报",
        "解放军报",
        "共青团中央",
        "中央广播电视总台",
        "微博管理员",
        "小红书官方",
    }
)


def _account_key(name: str) -> str:
    n = name.strip().lstrip("@")
    return n.casefold() if n.isascii() else n


def _is_generic_account(name: str) -> bool:
    if not name:
        return True
    key = _account_key(name)
    return key in {_account_key(g) for g in GENERIC_HANDLES}


def extract_entities(
    weibo_items: List[Dict[str, Any]],
    xiaohongshu_items: List[Dict[str, Any]],
    *,
    zhihu_items: Optional[List[Dict[str, Any]]] = None,
    max_weibo_users: int = 5,
    max_xiaohongshu_topics: int = 3,
    max_zhihu_questions: int = 5,
) -> Dict[str, List[str]]:
    """Extract key entities from Phase 1 results for supplemental searches.

    Parses Weibo for @用户, 小红书 for #话题# (double-hash topics), Zhihu for 问题标题.

    Args:
        weibo_items: Raw Weibo item dicts from Phase 1
        xiaohongshu_items: Raw 小红书 item dicts from Phase 1
        zhihu_items: Raw 知乎 item dicts (optional; used for question titles)
        max_weibo_users: Max Weibo users to return
        max_xiaohongshu_topics: Max 小红书话题 to return
        max_zhihu_questions: Max 知乎问题 strings to return

    Returns:
        Dict with keys: weibo_users, xiaohongshu_topics, zhihu_questions.
    """
    if zhihu_items is None:
        zhihu_items = []

    users = _extract_weibo_users(weibo_items)
    topics = _extract_xiaohongshu_topics(xiaohongshu_items)
    questions = _extract_zhihu_questions(zhihu_items)

    wu = users[:max_weibo_users]
    xt = topics[:max_xiaohongshu_topics]
    zq = questions[:max_zhihu_questions]
    return {
        "weibo_users": wu,
        "xiaohongshu_topics": xt,
        "zhihu_questions": zq,
    }


def _extract_weibo_users(weibo_items: List[Dict[str, Any]]) -> List[str]:
    """Extract and rank @用户 from Weibo results (author + @mentions in text)."""
    handle_counts = Counter()
    canonical: Dict[str, str] = {}
    mention_re = re.compile(r"@([\w\u4e00-\u9fff·]{1,40})")

    def bump(raw: str) -> None:
        raw = str(raw).strip().lstrip("@")
        if not raw or _is_generic_account(raw):
            return
        nk = _account_key(raw)
        if nk not in canonical:
            canonical[nk] = raw
        handle_counts[nk] += 1

    for item in weibo_items:
        bump(item.get("author_handle", "") or item.get("author", ""))
        text = item.get("text", "") or item.get("title", "") or ""
        for m in mention_re.findall(text):
            bump(m)

    return [canonical[k] for k, _ in handle_counts.most_common()]


def _extract_xiaohongshu_topics(xiaohongshu_items: List[Dict[str, Any]]) -> List[str]:
    """Extract and rank #话题# (double-hash) topics from 小红书 items."""
    topic_counts = Counter()
    topic_re = re.compile(r"#([^#\n][^#]{1,50}?)#")

    for item in xiaohongshu_items:
        chunks = []
        for field in ("text", "title", "caption_snippet", "description"):
            v = item.get(field)
            if v:
                chunks.append(str(v))
        blob = "\n".join(chunks)
        for raw in topic_re.findall(blob):
            t = raw.strip()
            if len(t) >= 2:
                topic_counts[t] += 1

        for tag in item.get("hashtags") or []:
            t = str(tag).strip().lstrip("#")
            if len(t) >= 2:
                topic_counts[t] += 1

    return [t for t, _ in topic_counts.most_common()]


def _extract_zhihu_questions(zhihu_items: List[Dict[str, Any]]) -> List[str]:
    """Extract and rank 知乎问题 titles from Zhihu items."""
    q_counts = Counter()

    for item in zhihu_items:
        q = item.get("question") or item.get("title")
        if not q:
            continue
        q = str(q).strip()
        if len(q) >= 4:
            q_counts[q] += 1

    return [q for q, _ in q_counts.most_common()]
