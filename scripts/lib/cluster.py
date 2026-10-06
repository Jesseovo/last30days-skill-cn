"""跨源聚类：把同一事件在多个平台上的条目聚合成一条热点。

复用 dedupe 的跨源相似度（``_get_cross_source_text`` + ``_hybrid_similarity``），
用并查集（union-find）求连通分量；仅保留覆盖 ≥2 个不同平台的簇，避免把单一
平台的近似条目当成"跨平台热点"。v4 起海外条目按 ``platform`` 区分来源。

Author: Jesse (https://github.com/Jesseovo)
"""

from typing import Any, Dict, List, Optional

from . import dedupe, schema, sources

# 平台类型 → 中文标签
_SOURCE_LABEL = {
    schema.WeiboItem: "微博",
    schema.XiaohongshuItem: "小红书",
    schema.BilibiliItem: "B站",
    schema.ZhihuItem: "知乎",
    schema.DouyinItem: "抖音",
    schema.WechatItem: "微信",
    schema.BaiduItem: "百度",
    schema.ToutiaoItem: "头条",
}


def source_label(item) -> str:
    if isinstance(item, schema.GlobalItem):
        return sources.platform_label(item.platform)
    return _SOURCE_LABEL.get(type(item), "?")


def _title_of(item) -> str:
    """取代表项的展示文本。"""
    for attr in ("title", "text"):
        value = getattr(item, attr, None)
        if value:
            return value.strip()[:80]
    return getattr(item, "url", "") or ""


def _rank_key(item):
    """簇代表项排序键：先看综合得分，再看相关性。"""
    return (getattr(item, "score", 0) or 0, getattr(item, "relevance", 0) or 0)


def build_clusters(*source_lists: List[Any], threshold: float = 0.40, query: Optional[str] = None) -> List[Dict[str, Any]]:
    """把多个平台的结果列表聚成跨平台簇。

    Args:
        *source_lists: 各平台已去重的条目列表。
        threshold: 跨源相似度阈值（与 dedupe.cross_source_link 保持一致）。
        query: 研究主题；比较前会去掉主题本身的词（所有结果都包含它，不能证明是同一事件）。

    Returns:
        簇列表，每个簇为 dict：
        ``{representative_id, representative_title, representative_url,
           member_ids, sources, size}``，按覆盖平台数、条目数降序。
    """
    all_items: List[Any] = []
    for source_list in source_lists:
        all_items.extend(source_list)

    n = len(all_items)
    if n <= 1:
        return []

    texts = [dedupe._get_cross_source_text(item) for item in all_items]
    keys = [dedupe.source_key(item) for item in all_items]
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]  # 路径压缩
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    # 只在不同平台之间连边（同源近似条目已由各自 dedupe 处理）
    for i in range(n):
        for j in range(i + 1, n):
            if keys[i] == keys[j]:
                continue
            if dedupe.event_similarity(texts[i], texts[j], query) >= threshold:
                union(i, j)

    groups: Dict[int, List[int]] = {}
    for idx in range(n):
        groups.setdefault(find(idx), []).append(idx)

    clusters: List[Dict[str, Any]] = []
    for members in groups.values():
        if len(members) < 2:
            continue
        member_items = [all_items[m] for m in members]
        if len({keys[m] for m in members}) < 2:
            continue  # 必须跨 ≥2 个平台
        rep = max(member_items, key=_rank_key)
        labels = sorted({source_label(it) for it in member_items})
        clusters.append({
            "representative_id": rep.id,
            "representative_title": _title_of(rep),
            "representative_url": getattr(rep, "url", "") or "",
            "member_ids": [it.id for it in member_items],
            "sources": labels,
            "size": len(member_items),
        })

    clusters.sort(key=lambda c: (len(c["sources"]), c["size"]), reverse=True)
    return clusters
