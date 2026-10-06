"""Opt-in overseas sources (#9): HN / GitHub / Reddit parsers and the upstream bridge."""

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from lib import github, hackernews, http, query, reddit, upstream_bridge  # noqa: E402


# --- query helpers ------------------------------------------------------------------

@pytest.mark.parametrize("topic,expected", [
    ("AI编程助手", None),                      # only a generic Latin token
    ("具身智能", None),
    ("Claude Code 评测", "Claude Code"),
    ("DeepSeek R2 发布", "DeepSeek R2"),
    ("What do people think about Claude Code?", "Claude Code"),
])
def test_overseas_query(topic, expected):
    assert query.overseas_query(topic) == expected


def test_overseas_query_override_wins():
    assert query.overseas_query("AI编程助手", "AI coding assistant") == "AI coding assistant"


@pytest.mark.parametrize("topic,expected", [
    ("AI编程助手", "AI编程助手"),            # v3 sent "ai 编程 助手"
    ("大家怎么看小米SU7", "小米SU7"),
    ("最新 Claude Code 编程助手 推荐", "Claude Code 编程助手"),
    ("推荐", "推荐"),
])
def test_search_keyword_keeps_case_and_adjacency(topic, expected):
    assert query.search_keyword(topic) == expected


# --- Hacker News ----------------------------------------------------------------------

def test_hackernews_hit_parsing():
    hit = {"objectID": "49814947", "title": "Claude Code reads AGENTS.md", "url": "https://blog.test/p",
           "author": "pszypowicz", "points": 486, "num_comments": 284, "created_at_i": 1790000000}
    parsed = hackernews.parse_hit(hit)
    assert parsed["url"] == "https://news.ycombinator.com/item?id=49814947"
    assert parsed["container"] == "blog.test"
    assert parsed["engagement"] == {"score": 486, "comments": 284}
    assert parsed["date"] == "2026-09-21"
    assert hackernews.parse_hit({"objectID": "1"}) == {}


def test_hackernews_search_uses_date_window():
    captured = {}

    def fake_get(url, **kwargs):
        captured["url"] = url
        return {"hits": [{"objectID": "1", "title": "Claude Code tips", "points": 10, "num_comments": 2,
                          "created_at_i": 1790000000}]}

    with patch.object(http, "get", side_effect=fake_get):
        items = hackernews.search_hackernews("Claude Code", "2026-09-03", "2026-10-03")
    assert "numericFilters=created_at_i" in captured["url"]
    assert items[0]["id"] == "HN1" and items[0]["relevance"] > 0.5


# --- GitHub ---------------------------------------------------------------------------

def test_github_repo_and_issue_parsing():
    repo = github.parse_repo({"full_name": "anthropics/claude-code", "description": "Agentic coding",
                              "html_url": "https://github.com/anthropics/claude-code", "stargazers_count": 59000,
                              "open_issues_count": 12, "pushed_at": "2026-10-01T10:00:00Z",
                              "created_at": "2025-02-01T00:00:00Z", "language": "TypeScript",
                              "owner": {"login": "anthropics"}})
    assert repo["title"].startswith("anthropics/claude-code: ")
    assert repo["engagement"]["stars"] == 59000 and repo["date"] == "2026-10-01"
    issue = github.parse_issue({"title": "Bug", "html_url": "https://github.com/o/r/issues/1",
                                "repository_url": "https://api.github.com/repos/o/r", "comments": 3,
                                "created_at": "2026-09-30T00:00:00Z", "reactions": {"total_count": 5},
                                "pull_request": {}, "user": {"login": "dev"}})
    assert issue["container"] == "o/r PR" and issue["engagement"] == {"likes": 5, "comments": 3}


def test_github_rate_limit_message():
    with patch.object(http, "get", side_effect=http.HTTPError("HTTP 403: rate limit", 403)):
        with pytest.raises(http.HTTPError) as exc:
            github.search_github("claude code", "2026-09-03", "2026-10-03")
    assert "GITHUB_TOKEN" in str(exc.value)


# --- Reddit ---------------------------------------------------------------------------

def test_reddit_post_parsing_and_window_filter():
    payload = {"data": {"children": [
        {"data": {"permalink": "/r/ClaudeAI/comments/1/x/", "title": "Claude Code workflow", "author": "u",
                  "subreddit_name_prefixed": "r/ClaudeAI", "score": 120, "num_comments": 33, "created_utc": 1790000000}},
        {"data": {"permalink": "/r/old/comments/2/y/", "title": "Claude Code old", "created_utc": 1600000000}},
    ]}}
    with patch.object(http, "get", return_value=payload):
        items = reddit.search_reddit("Claude Code", "2026-09-03", "2026-10-03")
    assert len(items) == 1
    assert items[0]["url"] == "https://www.reddit.com/r/ClaudeAI/comments/1/x/"
    assert items[0]["container"] == "r/ClaudeAI" and items[0]["id"] == "RD1"


def test_reddit_403_explains_datacenter_blocking():
    with patch.object(http, "get", side_effect=http.HTTPError("HTTP 403: Blocked", 403)):
        with pytest.raises(http.HTTPError) as exc:
            reddit.search_reddit("Claude Code", "2026-09-03", "2026-10-03")
    assert "403" in str(exc.value) and "upstream" in str(exc.value)


# --- upstream bridge -------------------------------------------------------------------

def _fake_upstream(root: Path, name: str = "last30days") -> Path:
    scripts = root / "skills" / "last30days" / "scripts"
    (scripts / "lib").mkdir(parents=True)
    (scripts / "lib" / "pipeline.py").write_text("# upstream marker\n", encoding="utf-8")
    script = scripts / "last30days.py"
    script.write_text("print('{}')\n", encoding="utf-8")
    (root / "skills" / "last30days" / "SKILL.md").write_text(f"---\nname: {name}\n---\n", encoding="utf-8")
    return script


def test_upstream_discovery_via_env_dir(tmp_path, monkeypatch):
    script = _fake_upstream(tmp_path)
    monkeypatch.setenv("LAST30DAYS_UPSTREAM", str(tmp_path))
    assert upstream_bridge.find_upstream() == script


def test_cn_skill_is_never_mistaken_for_upstream(tmp_path, monkeypatch):
    _fake_upstream(tmp_path, name="last30days-cn")
    monkeypatch.setenv("LAST30DAYS_UPSTREAM", str(tmp_path))
    assert upstream_bridge.find_upstream() is None
    this_skill = Path(__file__).resolve().parents[1] / "scripts" / "last30days.py"
    assert not upstream_bridge.is_upstream_script(this_skill)


def test_build_command_passes_window_and_platforms(tmp_path):
    cmd = upstream_bridge.build_command(tmp_path / "last30days.py", "python3", "Claude Code",
                                       "2026-09-03", "2026-10-03", "quick", ["x", "youtube"])
    assert cmd[2] == "Claude Code"
    assert cmd[cmd.index("--days") + 1] == "30" and cmd[cmd.index("--as-of") + 1] == "2026-10-03"
    assert cmd[cmd.index("--search") + 1] == "x,youtube" and "--quick" in cmd
    assert cmd[cmd.index("--json-profile") + 1] == "raw"


def test_map_items_normalizes_engagement_keys():
    payload = {
        "items_by_source": {
            "x": [{"source": "x", "title": "Thread", "url": "https://x.com/a/status/1", "author": "a",
                   "published_at": "2026-09-30T12:00:00Z", "engagement": {"likes": 10, "retweets": 2, "replies": 3}}],
            "youtube": [{"title": "Video", "url": "https://youtu.be/1", "engagement": {"views": 1000}},
                        {"title": "", "url": ""}],
        },
        "errors_by_source": {"tiktok": "skipped-unconfigured"},
    }
    items, errors = upstream_bridge.map_items(payload)
    assert len(items) == 2 and errors == {"tiktok": "skipped-unconfigured"}
    x_item = items[0]
    assert x_item["platform"] == "x" and x_item["date"] == "2026-09-30"
    assert x_item["engagement"] == {"likes": 10, "reposts": 2, "comments": 3}
    assert items[1]["engagement"] == {"views": 1000}


def test_search_upstream_reports_missing_install(monkeypatch):
    monkeypatch.setattr(upstream_bridge, "find_upstream", lambda: None)
    with pytest.raises(http.HTTPError) as exc:
        upstream_bridge.search_upstream("Claude Code", "2026-09-03", "2026-10-03")
    assert "mvanhorn/last30days-skill" in str(exc.value)


def test_search_upstream_parses_subprocess_json(tmp_path, monkeypatch):
    script = _fake_upstream(tmp_path)
    payload = {"items_by_source": {"x": [{"title": "Claude Code thread", "url": "https://x.com/a/status/1"}]}}

    class Done:
        returncode = 0
        stdout = "log line\n" + json.dumps(payload)
        stderr = ""

    monkeypatch.setattr(upstream_bridge, "find_upstream", lambda: script)
    monkeypatch.setattr(upstream_bridge, "upstream_python", lambda: ("python3", "ok"))
    with patch("lib.upstream_bridge.subprocess.run", return_value=Done()) as run:
        items = upstream_bridge.search_upstream("Claude Code", "2026-09-03", "2026-10-03", platforms=["x"])
    assert items[0]["id"] == "UP1" and items[0]["relevance"] >= 0.4
    assert run.call_args.kwargs["cwd"] == str(script.parent)
