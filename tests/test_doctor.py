"""Tests for doctor-style diagnostics (network probes are always mocked)."""

import sys
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib import doctor  # noqa: E402

_NO_BROWSER = {
    "playwright_available": False,
    "cached_logins": [],
    "logins": {},
    "cookie_dir": "cookies",
    "browser": {"mode": "managed"},
}


def _build(config, **overrides):
    probes = {
        "lib.doctor.env.probe_weibo_hot": True,
        "lib.doctor.env.probe_bilibili": True,
        "lib.doctor.env.probe_zhihu": True,
        "lib.doctor.env.probe_wechat": True,
        "lib.doctor.env.probe_toutiao": True,
        "lib.doctor.env.xiaohongshu_paths": {"mcp": False, "browser": False, "browser_logged_in": False, "site_search": True},
        "lib.doctor.env.discover_xiaohongshu_mcp": None,
        "lib.doctor.crawler_bridge.get_crawler_status": _NO_BROWSER,
        "lib.doctor.crawler_bridge.has_login": False,
    }
    probes.update(overrides)
    with ExitStack() as stack:
        for target, value in probes.items():
            stack.enter_context(patch(target, return_value=value))
        return doctor.build_report(config)


def test_doctor_errors_include_fix_cli_when_source_has_no_working_path():
    report = _build({}, **{"lib.doctor.env.probe_bilibili": False})
    errors = [s for s in report["sources"] if s["status"] == "error"]
    assert errors
    assert all(s["fix_cli"] for s in errors)
    assert any(s["source"] == "bilibili" for s in errors)


def test_doctor_marks_login_only_platforms_as_degraded_not_ok():
    report = _build({})
    by_source = {s["source"]: s for s in report["sources"]}
    for source in ("weibo", "xiaohongshu", "zhihu", "douyin"):
        assert by_source[source]["status"] == "warn", source
        assert "login" in by_source[source]["fix_cli"] or "playwright" in by_source[source]["fix_cli"]


def test_doctor_reports_configured_credentials_as_ok():
    report = _build({"WEIBO_COOKIE": "SUB=x", "ZHIHU_COOKIE": "z_c0=y", "TIKHUB_API_KEY": "k", "BAIDU_API_KEY": "b"})
    by_source = {s["source"]: s for s in report["sources"]}
    for source in ("weibo", "zhihu", "douyin", "baidu"):
        assert by_source[source]["status"] == "ok", source


def test_doctor_render_json_keeps_machine_fields():
    report = {
        "summary": {"ok": 1, "warn": 1, "error": 0},
        "sources": [
            {
                "source": "weibo",
                "label": "微博",
                "status": "ok",
                "available": True,
                "reason": "ok",
                "fix": "",
                "fix_cli": "",
            }
        ],
        "crawler_engine": {"playwright_available": True, "cached_logins": ["weibo"]},
        "notes": [],
    }
    payload = doctor.render_json(report)
    assert payload["summary"]["ok"] == 1
    assert payload["sources"][0]["source"] == "weibo"
    assert "crawler_engine" in payload


def test_doctor_render_text_mentions_login_and_overseas_sections():
    text = doctor.render_text(_build({}))
    assert "登录态" in text
    assert "海外源" in text
    assert "公开搜索兜底引擎" in text
