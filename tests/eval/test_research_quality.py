"""Offline labelled research cases, replayed at the source adapter boundary."""

import io
import json
import sys
from contextlib import redirect_stdout
from datetime import date, datetime, timedelta
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from unittest.mock import patch

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "scripts"))
import last30days
from lib import dates, pipeline, query, query_type, render, schema, sources

CASES = sorted((HERE / "cases").glob("*.json"))


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def replay(case):
    # The run finishes just after midnight in Beijing (previous UTC day).
    instant = datetime.fromisoformat(case["as_of"] + "T00:05:00+08:00")

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return instant.astimezone(tz) if tz else instant.replace(tzinfo=None)

    release = Event()

    def adapter(source):
        def search(ctx):
            if source in case["timeouts"]:
                release.wait()
            return case["items"][source]

        return search

    limits = {source + "_future": 0 for source in case["timeouts"]}
    active = list(case["items"])
    adapters = {source: adapter(source) for source in active}
    with patch.object(dates, "datetime", Clock), patch.object(
        schema, "datetime", Clock
    ):
        start, end = dates.get_date_range(case["days"])
        topic = case["topic"]
        ctx = pipeline.RunContext(topic, query.search_keyword(topic), start, end)
        kind = query_type.detect_query_type(topic)
        try:
            with patch.object(pipeline, "SEARCHERS", adapters):
                raw = pipeline.run_sources(ctx, active, limits, log=False)
        finally:
            release.set()
        processed = pipeline.process_results(raw, start, end, kind)
        report = pipeline.build_report(topic, ctx, raw, processed, kind)
        report.context_snippet_md = render.render_context_snippet(report)
        output = io.StringIO()
        with redirect_stdout(output):
            last30days._emit(SimpleNamespace(emit="json", save_dir=None), report)
    result = json.loads(output.getvalue())
    # Wall time measures the host scheduler, not research quality.
    for status in result["source_status"].values():
        del status["elapsed"]
    return result


def test_fixture_matrix():
    cases = [read(path) for path in CASES]
    assert {sid for case in cases for sid in case["items"]} == set(
        sources.CN_SOURCE_IDS
    )
    assert {path.stem for path in CASES} == set(read(HERE / "baseline.json"))
    assert any(not any(case["items"].values()) for case in cases)


def check_top_five(source, rows, relevant, previous):
    head = [row["id"] for row in rows[:5]]
    hits = relevant.intersection(head)
    previous_hits = relevant.intersection(previous)
    detail = (
        source,
        "displaced",
        sorted(previous_hits - hits),
        "baseline",
        previous,
        "current",
        head,
    )
    assert len(hits) >= len(previous_hits), detail
    # Compare precision as well as hit count for sources returning fewer than five.
    assert len(hits) * len(previous) >= len(previous_hits) * len(head), detail
    label = "{}/{}".format(len(hits), len(head)) if head else "N/A(0)"
    return "{}={}".format(source, label)


def check_clusters(result, seen, expected):
    clusters = result.get("clusters", [])
    groups = [set(group) for group in expected["clusters"]]
    assert sorted(sorted(c["member_ids"]) for c in clusters) == sorted(
        sorted(group) for group in groups
    )
    for a, b in expected["separate"]:
        assert a in seen and b in seen
        assert not any({a, b} <= set(c["member_ids"]) for c in clusters)
    for cluster in clusters:
        rep = cluster["representative_id"]
        assert rep in cluster["member_ids"]
        assert cluster["representative_url"] == seen[rep]["url"]
    for key, row in seen.items():
        # The labelled clusters here contain direct corroborating pairs.
        peers = {
            peer for group in groups if key in group for peer in group if peer != key
        }
        assert set(row.get("cross_refs", [])) == peers


@pytest.mark.parametrize("path", CASES, ids=lambda path: path.stem)
def test_research_quality(path):
    case = read(path)
    expected = case["expected"]
    result = replay(case)
    assert result == replay(case)
    end = date.fromisoformat(case["as_of"])
    start = end - timedelta(days=case["days"])
    assert result["range"] == {"from": start.isoformat(), "to": end.isoformat()}
    assert set(result["source_status"]) == set(case["items"])
    assert not any(
        result[sid] for sid in set(sources.CN_SOURCE_IDS) - set(case["items"])
    )

    seen = {}
    known = 0
    baseline = read(HERE / "baseline.json")[path.stem]
    assert set(baseline) == set(case["items"])
    top5 = []
    for sid, inputs in case["items"].items():
        origins = {row["id"]: row for row in inputs}
        assert len(origins) == len(inputs)
        rows = result[sid]
        status = result["source_status"][sid]
        assert status["state"] == expected["states"][sid]
        assert status["raw_count"] == len(inputs)
        assert status["count"] == len(rows)
        if status["state"] == "timeout":
            assert status["error"] and not rows

        for row in rows:
            key = row["id"]
            assert key not in seen and sources.source_for_item_id(key) == sid
            origin = origins[key]
            assert row["url"] == origin["url"] and row["url"]
            text_field = "text" if sid in {"weibo", "douyin"} else "title"
            assert row[text_field] == origin[text_field]
            assert row["date"] == origin["date"]
            if row["date"] is None:
                assert row["date_confidence"] == "low"
            else:
                assert start <= date.fromisoformat(row["date"]) <= end
                known += 1
            seen[key] = row

        top5.append(check_top_five(sid, rows, set(expected["relevant"]), baseline[sid]))

    assert set(expected["keep"]) <= seen.keys()
    assert not set(expected["exclude"]).intersection(seen)
    check_clusters(result, seen, expected)

    print(
        "{} | linked={} known={} undated={} | {} | clusters={} states={} stable".format(
            path.stem,
            len(seen),
            known,
            len(seen) - known,
            " ".join(top5),
            len(result.get("clusters", [])),
            ",".join(status["state"] for status in result["source_status"].values()),
        )
    )
