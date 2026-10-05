"""Config loading, Python 3.8 guard and CLI entry points (v4)."""

import os
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import last30days  # noqa: E402
from lib import env, trending  # noqa: E402


# --- .env handling -----------------------------------------------------------------

def test_runtime_switches_in_env_file_are_honoured(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# comment\nexport LAST30DAYS_DISABLE_BROWSER=1\nEXCLUDE_SOURCES='douyin'\nWEIBO_COOKIE=\"SUB=abc\"\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(env, "CONFIG_FILE", env_file)
    monkeypatch.setattr(env, "_find_project_env", lambda: None)
    for key in ("LAST30DAYS_DISABLE_BROWSER", "EXCLUDE_SOURCES", "WEIBO_COOKIE"):
        monkeypatch.delenv(key, raising=False)
    config = env.get_config()
    assert config["WEIBO_COOKIE"] == "SUB=abc"
    assert os.environ["LAST30DAYS_DISABLE_BROWSER"] == "1"
    assert os.environ["EXCLUDE_SOURCES"] == "douyin"


def test_process_environment_wins_over_env_file(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("EXCLUDE_SOURCES=douyin\n", encoding="utf-8")
    monkeypatch.setattr(env, "CONFIG_FILE", env_file)
    monkeypatch.setattr(env, "_find_project_env", lambda: None)
    monkeypatch.setenv("EXCLUDE_SOURCES", "baidu")
    env.get_config()
    assert os.environ["EXCLUDE_SOURCES"] == "baidu"


def test_secrets_are_not_exported_to_the_environment(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("ZHIHU_COOKIE=z_c0=secret\n", encoding="utf-8")
    monkeypatch.setattr(env, "CONFIG_FILE", env_file)
    monkeypatch.setattr(env, "_find_project_env", lambda: None)
    monkeypatch.delenv("ZHIHU_COOKIE", raising=False)
    assert env.get_config()["ZHIHU_COOKIE"] == "z_c0=secret"
    assert "ZHIHU_COOKIE" not in os.environ


def test_xhs_mcp_base_only_when_configured_or_reachable(monkeypatch):
    assert env.get_xiaohongshu_api_base({}) is None
    assert env.get_xiaohongshu_api_base({"XIAOHONGSHU_API_BASE": "http://h:18060/"}) == "http://h:18060"
    assert env.discover_xiaohongshu_mcp({"XIAOHONGSHU_API_BASE": "http://h:18060"}) == "http://h:18060"


def test_baidu_api_needs_only_the_key():
    assert env.is_baidu_api_available({"BAIDU_API_KEY": "k"})
    assert not env.is_baidu_api_available({"BAIDU_SECRET_KEY": "s"})


# --- Python 3.8 guard (issue #13) ---------------------------------------------------

_BUILTIN_GENERICS = {"list", "dict", "tuple", "set", "frozenset", "type"}
_PAREN_WITH = re.compile(r"^\s*with \($", re.M)


def _runtime_annotations(tree):
    """Annotations Python evaluates at definition time (no __future__ import)."""
    import ast

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = node.args
            for arg in args.args + args.kwonlyargs + getattr(args, "posonlyargs", []):
                if arg.annotation is not None:
                    yield arg.annotation
            for arg in (args.vararg, args.kwarg):
                if arg is not None and arg.annotation is not None:
                    yield arg.annotation
            if node.returns is not None:
                yield node.returns
        elif isinstance(node, ast.AnnAssign):
            yield node.annotation


def _py39_offences(path: Path):
    import ast

    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    found = []
    if "from __future__ import annotations" not in source:
        for annotation in _runtime_annotations(tree):
            for sub in ast.walk(annotation):
                if isinstance(sub, ast.Subscript) and isinstance(sub.value, ast.Name) and sub.value.id in _BUILTIN_GENERICS:
                    found.append(f"{path.name}:{sub.lineno} PEP 585 `{sub.value.id}[...]` annotation")
                if isinstance(sub, ast.BinOp) and isinstance(sub.op, ast.BitOr):
                    found.append(f"{path.name}:{sub.lineno} PEP 604 `X | Y` annotation")
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in ("removeprefix", "removesuffix"):
            found.append(f"{path.name}:{node.lineno} str.{node.attr} (3.9)")
    if _PAREN_WITH.search(source):
        found.append(f"{path.name}: parenthesized context managers (3.10)")
    return found


def test_sources_avoid_python39_only_constructs():
    files = list((REPO_ROOT / "scripts").rglob("*.py")) + list((REPO_ROOT / "tests").rglob("*.py"))
    offenders = [offence for path in files for offence in _py39_offences(path)]
    assert not offenders, offenders


# --- CLI ----------------------------------------------------------------------------

def _run_cli(*args, env_overrides=None):
    environment = dict(os.environ)
    environment.update({"PYTHONIOENCODING": "utf-8"})
    environment.update(env_overrides or {})
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "last30days.py"), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace", env=environment, timeout=60,
    )


def test_cli_version_and_help():
    from lib.version import DISPLAY_VERSION
    version = _run_cli("--version")
    assert version.returncode == 0 and DISPLAY_VERSION in version.stdout
    help_text = _run_cli("--help").stdout
    for flag in ("--hot", "--global", "--global-query", "--no-browser", "--probe-browser"):
        assert flag in help_text


def test_cli_login_usage_errors(tmp_path):
    result = _run_cli("login", "myspace", env_overrides={"LAST30DAYS_CN_CONFIG_DIR": str(tmp_path)})
    assert result.returncode == 1 and "login <" in result.stderr


def test_cli_login_cookie_import(tmp_path):
    result = _run_cli("login", "zhihu", "--cookie", "z_c0=abc; _xsrf=1",
                      env_overrides={"LAST30DAYS_CN_CONFIG_DIR": str(tmp_path)})
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "browser_cookies" / "zhihu_cookies.json").exists()


def test_cli_requires_topic():
    result = _run_cli()
    assert result.returncode == 1 and "--hot" in result.stderr


def test_hot_mode_dispatch_writes_outputs(tmp_path, monkeypatch, capsys):
    data = {"generated_at": "2026-10-03 22:00", "timezone": "Asia/Shanghai", "topic_filter": "国足",
            "boards": {"weibo": {"label": "微博热搜", "kind": "board",
                                 "items": [{"rank": 1, "title": "国足夺铜", "url": "https://s.weibo.com/x"}]}},
            "topics": []}
    monkeypatch.setattr(last30days.render, "OUTPUT_DIR", tmp_path)
    monkeypatch.setenv("LAST30DAYS_OUTPUT_DIR", str(tmp_path))
    args = SimpleNamespace(hot_sources="weibo", hot_limit=10, hot_title="热榜", emit="compact", save_dir=None)
    with patch.object(trending, "build", return_value=data) as build:
        assert last30days._run_hot(args, "国足") == 0
    build.assert_called_once_with(["weibo"], limit=10, topic="国足")
    assert "国足夺铜" in capsys.readouterr().out
    assert (tmp_path / "hot.html").exists()


def test_hot_mode_rejects_unknown_board(capsys):
    args = SimpleNamespace(hot_sources="weibo,nope", hot_limit=10, hot_title="热榜", emit="compact", save_dir=None)
    assert last30days._run_hot(args, "") == 1
    assert "未知热榜来源" in capsys.readouterr().err
