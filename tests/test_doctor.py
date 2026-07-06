"""Tests for doctor-style diagnostics."""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib import doctor


def test_doctor_errors_include_fix_cli_when_source_has_no_working_path():
    config = {}
    with (
        patch("lib.doctor.env.is_weibo_available", return_value=False),
        patch("lib.doctor.env.is_xiaohongshu_available", return_value=True),
        patch("lib.doctor.env.probe_bilibili", return_value=False),
        patch("lib.doctor.env.probe_zhihu", return_value=True),
        patch("lib.doctor.env.is_douyin_available", return_value=False),
        patch("lib.doctor.env.is_wechat_available", return_value=False),
        patch("lib.doctor.env.is_baidu_api_available", return_value=False),
        patch("lib.doctor.env.probe_toutiao", return_value=True),
        patch("lib.doctor.crawler_bridge.get_crawler_status", return_value={
            "playwright_available": False,
            "cached_logins": [],
            "cookie_dir": "cookies",
        }),
    ):
        report = doctor.build_report(config)

    errors = [s for s in report["sources"] if s["status"] == "error"]
    assert errors
    assert all(s["fix_cli"] for s in errors)
    assert any(s["source"] == "bilibili" for s in errors)


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
