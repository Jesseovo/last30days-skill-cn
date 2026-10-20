"""全网热榜 / 热点发现（issue #16）。

Author: Jesse (https://github.com/Jesseovo)

``python scripts/last30days.py --hot`` 不需要输入主题：并行抓取微博热搜、百度热搜、
抖音热榜、头条热榜、B站热搜、知乎热榜（以及可选的科技资讯 RSS / Hacker News），
把同一事件在多个平台上的热搜合并成「跨平台热点」，输出 Markdown / JSON / 静态
HTML 看板。配合 ``.github/workflows/daily-hot.yml`` 可以每天自动发布到 GitHub Pages，
得到一个「只看每天热点」的现成网站。

自定义 RSS（例如自建 RSSHub 的 36 氪快讯、X/Twitter 列表）：
``LAST30DAYS_HOT_FEEDS="36氪快讯|https://your-rsshub/36kr/newsflashes,..."``
"""

import json
import os
import re
import sys
import threading
import time
import xml.etree.ElementTree as ET
from collections import OrderedDict
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from . import baidu, bilibili, dates, douyin, hackernews, http, relevance, toutiao, weibo, zhihu
from .version import DISPLAY_VERSION

BOARDS: "OrderedDict[str, Tuple[str, str, Callable[[int], List[Dict[str, Any]]]]]" = OrderedDict([
    ("weibo", ("微博热搜", "WEIBO", weibo.fetch_hot)),
    ("baidu", ("百度热搜", "BAIDU", baidu.fetch_hot)),
    ("douyin", ("抖音热榜", "DOUYIN", douyin.fetch_hot)),
    ("toutiao", ("头条热榜", "TOUTIAO", toutiao.fetch_hot)),
    ("bilibili", ("B站热搜", "BILI", bilibili.fetch_hot)),
    ("zhihu", ("知乎热榜", "ZHIHU", zhihu.fetch_hot)),
    ("hackernews", ("Hacker News", "HN", hackernews.fetch_front_page)),
])
FEEDS: "OrderedDict[str, Tuple[str, str]]" = OrderedDict([
    ("ithome", ("IT之家", "https://www.ithome.com/rss/")),
    ("huxiu", ("虎嗅", "https://rss.huxiu.com/")),
    ("sspai", ("少数派", "https://sspai.com/feed")),
    ("ifanr", ("爱范儿", "https://www.ifanr.com/feed")),
    ("solidot", ("Solidot", "https://www.solidot.org/index.rss")),
])
CN_BOARDS: Tuple[str, ...] = ("weibo", "baidu", "douyin", "toutiao", "bilibili", "zhihu")
GROUPS: Dict[str, Tuple[str, ...]] = {
    "boards": CN_BOARDS,
    "cn": CN_BOARDS,
    "news": tuple(FEEDS),
    "global": ("hackernews",),
    "all": CN_BOARDS + tuple(FEEDS) + ("hackernews",),
}
DEFAULT_SOURCES: Tuple[str, ...] = CN_BOARDS
SOURCES_ENV = "LAST30DAYS_HOT_SOURCES"
CUSTOM_FEEDS_ENV = "LAST30DAYS_HOT_FEEDS"
FETCH_TIMEOUT = 20


class UnknownHotSource(ValueError):
    pass


def custom_feeds() -> "OrderedDict[str, Tuple[str, str]]":
    """Parse ``LAST30DAYS_HOT_FEEDS="名称|url,名称|url"``."""
    feeds: "OrderedDict[str, Tuple[str, str]]" = OrderedDict()
    raw = os.environ.get(CUSTOM_FEEDS_ENV, "").strip()
    for idx, part in enumerate(p for p in raw.split(",") if p.strip()):
        name, _, url = part.partition("|")
        url = url.strip() or name.strip()
        name = name.strip() if url != name.strip() else f"RSS{idx + 1}"
        if url.startswith(("http://", "https://")):
            feeds[f"feed{idx + 1}"] = (name or f"RSS{idx + 1}", url)
    return feeds


def parse_sources(text: Optional[str]) -> List[str]:
    """Resolve ``--hot-sources`` (board ids, feed ids and group names)."""
    raw = (text or os.environ.get(SOURCES_ENV, "")).strip()
    extra_feeds = custom_feeds()
    if not raw:
        return list(DEFAULT_SOURCES) + list(extra_feeds)
    out: List[str] = []
    for token in raw.split(","):
        key = token.strip().lower()
        if not key:
            continue
        if key in GROUPS:
            candidates = list(GROUPS[key])
        elif key in BOARDS or key in FEEDS or key in extra_feeds:
            candidates = [key]
        elif key in ("custom", "feeds"):
            candidates = list(extra_feeds)
        else:
            raise UnknownHotSource(key)
        for cid in candidates:
            if cid not in out:
                out.append(cid)
    return out


def describe_sources() -> str:
    names = [f"{k}({v[0]})" for k, v in BOARDS.items()] + [f"{k}({v[0]})" for k, v in FEEDS.items()]
    return "、".join(names) + "；分组：boards/news/global/all；自定义 RSS：LAST30DAYS_HOT_FEEDS"


# ---------------------------------------------------------------------------
# RSS / Atom
# ---------------------------------------------------------------------------

def _strip_ns(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _parse_feed_date(text: str) -> Optional[str]:
    text = (text or "").strip()
    if not text:
        return None
    try:
        dt = parsedate_to_datetime(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=dates.CST)
        return dt.astimezone(dates.CST).strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError, IndexError):
        pass
    match = re.match(r"(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2})", text)
    if match:
        return f"{match.group(1)} {match.group(2)}"
    return None


def parse_feed(body: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Parse RSS 2.0 / Atom into ``{rank,title,url,published,label}`` rows."""
    text = re.sub(r"^\s*<\?xml[^>]*\?>", "", body or "").strip()
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return []
    rows = []
    for node in root.iter():
        tag = _strip_ns(node.tag)
        if tag not in ("item", "entry"):
            continue
        title = link = published = ""
        for child in node:
            ctag = _strip_ns(child.tag)
            if ctag == "title":
                title = (child.text or "").strip()
            elif ctag == "link":
                link = (child.text or "").strip() or child.attrib.get("href", "")
            elif ctag in ("pubDate", "published", "updated", "date") and not published:
                published = child.text or ""
        title = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", title)).strip()
        if title and link:
            rows.append({"title": title, "url": link.strip(), "published": _parse_feed_date(published)})
    rows.sort(key=lambda r: r.get("published") or "", reverse=True)
    out = []
    for rank, row in enumerate(rows[:limit], start=1):
        row.update({"rank": rank, "hot_value": None, "label": (row.get("published") or "")[5:]})
        out.append(row)
    return out


def _fetch_feed(url: str, limit: int) -> List[Dict[str, Any]]:
    body = http.get_text(url, headers=http.browser_headers(), timeout=15)
    return parse_feed(body, limit)


# ---------------------------------------------------------------------------
# Fetch + merge
# ---------------------------------------------------------------------------

def _label_for(source_id: str) -> Tuple[str, str, str]:
    """(label, code, kind) for a board or feed id."""
    if source_id in BOARDS:
        label, code, _ = BOARDS[source_id]
        return label, code, "board"
    feeds = OrderedDict(list(FEEDS.items()) + list(custom_feeds().items()))
    if source_id in feeds:
        return feeds[source_id][0], "RSS", "feed"
    return source_id, source_id.upper(), "board"


def fetch_all(source_ids: Sequence[str], limit: int = 20, log: bool = True) -> "OrderedDict[str, Dict[str, Any]]":
    """Fetch all boards/feeds in parallel with a per-source deadline."""
    feeds = OrderedDict(list(FEEDS.items()) + list(custom_feeds().items()))
    results: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
    boxes: Dict[str, Dict[str, Any]] = {}
    threads: Dict[str, threading.Thread] = {}
    started = time.monotonic()

    for sid in source_ids:
        label, code, kind = _label_for(sid)
        box: Dict[str, Any] = {"label": label, "code": code, "kind": kind}
        boxes[sid] = box

        def worker(sid=sid, box=box, kind=kind):
            t0 = time.monotonic()
            try:
                if kind == "feed":
                    box["items"] = _fetch_feed(feeds[sid][1], limit)
                else:
                    box["items"] = BOARDS[sid][2](limit)[:limit]
                box["error"] = None if box["items"] else "未返回条目"
            except Exception as exc:
                box["items"] = []
                box["error"] = str(exc) if isinstance(exc, http.HTTPError) else f"{type(exc).__name__}: {exc}"
            box["elapsed"] = round(time.monotonic() - t0, 1)

        thread = threading.Thread(target=worker, name=f"hot-{sid}", daemon=True)
        thread.start()
        threads[sid] = thread

    for sid, thread in threads.items():
        thread.join(max(0.0, FETCH_TIMEOUT - (time.monotonic() - started)))
        box = boxes[sid]
        if thread.is_alive():
            box.update(items=[], error=f"超时（{FETCH_TIMEOUT}s）", elapsed=float(FETCH_TIMEOUT))
        results[sid] = box
        if log:
            if box.get("error") and not box.get("items"):
                sys.stderr.write(f"[{box['label']}] 获取失败: {box['error']}\n")
            else:
                sys.stderr.write(f"[{box['label']}] {len(box['items'])} 条\n")
    return results


_PUNCT_RE = re.compile(r"[\s#＃\"“”'‘’《》<>【】\[\]()（）,，.。!！?？:：;；、·…—\-_/|]+")


def _norm_title(title: str) -> str:
    return _PUNCT_RE.sub("", (title or "").lower())


def _shingles(text: str) -> set:
    if len(text) < 2:
        return {text} if text else set()
    return {text[i:i + 2] for i in range(len(text) - 1)}


def titles_match(a: str, b: str) -> bool:
    """Cheap near-duplicate test (identical / containment / high bigram Dice)."""
    na, nb = _norm_title(a), _norm_title(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    if min(len(na), len(nb)) >= 4 and (na in nb or nb in na):
        return True
    sa, sb = _shingles(na), _shingles(nb)
    if not sa or not sb:
        return False
    dice = 2 * len(sa & sb) / (len(sa) + len(sb))
    return dice >= 0.6


# Characters that make a CJK bigram uninformative when both halves are function words.
_FUNCTION_CHARS = set("如何评价怎么看为什么哪些是否这那我们他们你一个已经还就可以没有不因为所以如果但能会有的了在和与及吗呢吧啊")
SALIENT_MATCH_THRESHOLD = 0.45


def salient_terms(title: str) -> set:
    """CJK bigrams + alphanumeric tokens (``u23``, ``169``) of a hot-list title."""
    text = (title or "").lower()
    terms = set()
    for run in re.findall(r"[一-鿿]+", text):
        for i in range(len(run) - 1):
            pair = run[i:i + 2]
            if pair[0] in _FUNCTION_CHARS and pair[1] in _FUNCTION_CHARS:
                continue
            terms.add(pair)
    for token in re.findall(r"[a-z0-9]+", text):
        if len(token) >= 2:
            terms.add(token)
    return terms


def _idf_table(term_sets: Sequence[set]) -> Dict[str, float]:
    import math

    total = max(1, len(term_sets))
    freq: Dict[str, int] = {}
    for terms in term_sets:
        for term in terms:
            freq[term] = freq.get(term, 0) + 1
    return {term: math.log(total / count) for term, count in freq.items()}


def salient_similarity(a: set, b: set, idf: Dict[str, float]) -> float:
    """IDF-weighted overlap coefficient; needs ≥2 shared terms."""
    shared = a & b
    if len(shared) < 2:
        return 0.0
    weight = sum(idf.get(t, 0.0) for t in shared)
    denom = min(sum(idf.get(t, 0.0) for t in a), sum(idf.get(t, 0.0) for t in b))
    return weight / denom if denom > 0 else 0.0


def merge_topics(boards: "OrderedDict[str, Dict[str, Any]]") -> List[Dict[str, Any]]:
    """Union same-event hot items across *different* boards (feeds excluded).

    Platforms phrase one event very differently ("中国男足获亚运铜牌" vs
    "拿下点球大战！U23国足获亚运铜牌"), so besides near-duplicate titles we
    compare IDF-weighted salient terms computed over the whole snapshot:
    rare shared terms ("铜牌", "u23", "169") count, common ones ("中国") don't.
    """
    entries: List[Tuple[str, Dict[str, Any], int]] = []
    for sid, board in boards.items():
        if board.get("kind") != "board" or sid == "hackernews":
            continue
        items = board.get("items") or []
        for item in items:
            if item.get("pinned"):
                continue
            entries.append((sid, item, len(items)))

    term_sets = [salient_terms(entry[1]["title"]) for entry in entries]
    idf = _idf_table(term_sets)
    parent = list(range(len(entries)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i in range(len(entries)):
        for j in range(i + 1, len(entries)):
            if entries[i][0] == entries[j][0]:
                continue
            if titles_match(entries[i][1]["title"], entries[j][1]["title"]) or (
                salient_similarity(term_sets[i], term_sets[j], idf) >= SALIENT_MATCH_THRESHOLD
            ):
                ri, rj = find(i), find(j)
                if ri != rj:
                    parent[rj] = ri

    groups: Dict[int, List[int]] = {}
    for idx in range(len(entries)):
        groups.setdefault(find(idx), []).append(idx)

    topics = []
    for members in groups.values():
        boards_hit = {entries[m][0] for m in members}
        if len(boards_hit) < 2:
            continue
        heat = 0.0
        best = None
        mentions = []
        for m in members:
            sid, item, size = entries[m]
            position = 1.0 - (max(1, item.get("rank") or 1) - 1) / max(1, size)
            heat += position
            mentions.append({
                "platform": sid,
                "label": boards[sid]["label"],
                "rank": item.get("rank"),
                "title": item["title"],
                "url": item.get("url", ""),
                "hot_value": item.get("hot_value"),
            })
            if best is None or position > best[0]:
                best = (position, item)
        mentions.sort(key=lambda x: (x["rank"] or 999))
        topics.append({
            "title": best[1]["title"],
            "url": best[1].get("url", ""),
            "platform_count": len(boards_hit),
            "score": round(heat + 0.75 * (len(boards_hit) - 1), 2),
            "mentions": mentions,
        })
    topics.sort(key=lambda t: (t["platform_count"], t["score"]), reverse=True)
    return topics


def filter_by_topic(boards: "OrderedDict[str, Dict[str, Any]]", topic: str) -> "OrderedDict[str, Dict[str, Any]]":
    """Keep only hot items related to ``topic`` (e.g. ``--hot "AI"``)."""
    needle = _norm_title(topic)
    filtered: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
    for sid, board in boards.items():
        kept = []
        for item in board.get("items") or []:
            title = item.get("title", "")
            if (needle and needle in _norm_title(title)) or relevance.token_overlap_relevance(topic, title) >= 0.3:
                kept.append(item)
        copy = dict(board)
        copy["items"] = kept
        filtered[sid] = copy
    return filtered


def build(source_ids: Sequence[str], limit: int = 20, topic: Optional[str] = None, log: bool = True) -> Dict[str, Any]:
    boards = fetch_all(source_ids, limit=limit, log=log)
    if topic:
        boards = filter_by_topic(boards, topic)
    now = datetime.now(dates.CST)
    return {
        "generated_at": now.strftime("%Y-%m-%d %H:%M"),
        "timezone": "Asia/Shanghai",
        "topic_filter": topic or "",
        "boards": boards,
        "topics": merge_topics(boards),
    }


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _fmt_hot(value: Any) -> str:
    if value in (None, "", 0):
        return ""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number >= 1e8:
        return f"{number / 1e8:.1f}亿"
    if number >= 1e4:
        return f"{number / 1e4:.1f}万"
    return f"{int(number)}"


def to_json(data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "generated_at": data["generated_at"],
        "timezone": data["timezone"],
        "topic_filter": data["topic_filter"],
        "topics": data["topics"],
        "boards": {
            sid: {
                "label": board.get("label"),
                "kind": board.get("kind"),
                "items": board.get("items") or [],
                "error": board.get("error") if not board.get("items") else None,
                "elapsed": board.get("elapsed"),
            }
            for sid, board in data["boards"].items()
        },
        "version": DISPLAY_VERSION,
    }


def render_markdown(data: Dict[str, Any], per_board: int = 15, max_topics: int = 15) -> str:
    title = "全网热榜" + (f" · 与「{data['topic_filter']}」相关" if data.get("topic_filter") else "")
    lines = [
        f"🔥 last30days-cn v{DISPLAY_VERSION} · {title} · {data['generated_at']}（北京时间）",
        "",
    ]
    topics = data.get("topics") or []
    if topics:
        lines.extend(["## 跨平台热点（多个平台同时在榜）", ""])
        for idx, topic in enumerate(topics[:max_topics], start=1):
            where = "、".join(f"{m['label']}#{m['rank']}" for m in topic["mentions"])
            lines.append(f"{idx}. **{topic['title']}** — {where}")
            if topic.get("url"):
                lines.append(f"   {topic['url']}")
        lines.append("")

    for sid, board in data["boards"].items():
        items = board.get("items") or []
        lines.append(f"## {board.get('label', sid)}")
        lines.append("")
        if not items:
            lines.extend([f"*不可用：{board.get('error') or '无数据'}*", ""])
            continue
        for item in items[:per_board]:
            extra = " ".join(x for x in (f"[{item['label']}]" if item.get("label") else "", _fmt_hot(item.get("hot_value"))) if x)
            lines.append(f"{item.get('rank', '-')}. {item['title']}{(' ' + extra) if extra else ''}")
            if item.get("url"):
                lines.append(f"   {item['url']}")
        lines.append("")

    lines.extend([
        "---",
        "*热榜是平台实时排行（非 30 天累计）。深入研究某个话题：*",
        "`python scripts/last30days.py \"<话题>\" --emit compact`",
        "",
    ])
    return "\n".join(lines)


def _href(url: str) -> str:
    cleaned = (url or "").strip()
    return cleaned if cleaned.lower().startswith(("http://", "https://")) else "#"


def render_html(data: Dict[str, Any], per_board: int = 20, max_topics: int = 24, site_title: str = "全网热榜") -> str:
    from .hot_board import render_page

    return render_page(data, per_board, max_topics, site_title, _fmt_hot, _href)


def write_outputs(data: Dict[str, Any], output_dir, title: str = "全网热榜") -> Dict[str, str]:
    """Write hot.md / hot.json / hot.html into ``output_dir``."""
    from pathlib import Path

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = {
        "md": out / "hot.md",
        "json": out / "hot.json",
        "html": out / "hot.html",
    }
    paths["md"].write_text(render_markdown(data), encoding="utf-8")
    paths["json"].write_text(json.dumps(to_json(data), ensure_ascii=False, indent=2), encoding="utf-8")
    paths["html"].write_text(render_html(data, site_title=title or "全网热榜"), encoding="utf-8")
    return {k: str(v) for k, v in paths.items()}
