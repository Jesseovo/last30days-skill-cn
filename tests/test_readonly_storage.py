"""Read-only HOME regressions (#36), without requiring a read-only mount."""

import errno
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import last30days
from lib import cache, crawler_bridge, render, trending


@pytest.fixture
def readonly_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    temp = tmp_path / "temp"
    home.mkdir()
    temp.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    monkeypatch.setattr(render, "OUTPUT_DIR", home / "out")
    monkeypatch.setattr(cache, "CACHE_DIR", home / "cache")
    monkeypatch.setattr(cache, "MODEL_CACHE_FILE", home / "cache" / "model_selection.json")
    monkeypatch.setattr(crawler_bridge, "COOKIE_DIR", home / "config" / "browser_cookies")
    monkeypatch.setenv("LAST30DAYS_CN_CONFIG_DIR", str(home / "config"))
    monkeypatch.delenv("LAST30DAYS_OUTPUT_DIR", raising=False)
    monkeypatch.delenv("LAST30DAYS_CACHE_DIR", raising=False)
    monkeypatch.setattr(render.tempfile, "gettempdir", lambda: str(temp))
    return home, temp


def block_home_writes(monkeypatch, home, error, existing):
    mkdir = Path.mkdir
    open_file = os.open
    access = os.access

    def denied_mkdir(path, *args, **kwargs):
        if path == home or home in path.parents:
            if not (existing and path.is_dir() and kwargs.get("exist_ok")):
                raise OSError(error, os.strerror(error), str(path))
        return mkdir(path, *args, **kwargs)

    def denied_open(path, flags, *args, **kwargs):
        if home in Path(path).parents and flags & (os.O_CREAT | os.O_WRONLY | os.O_RDWR):
            raise OSError(error, os.strerror(error), str(path))
        return open_file(path, flags, *args, **kwargs)

    def denied_access(path, mode, *args, **kwargs):
        # Windows tempfile retries EACCES when access() still reports writable.
        if (Path(path) == home or home in Path(path).parents) and mode & os.W_OK:
            return False
        return access(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", denied_mkdir)
    monkeypatch.setattr(os, "open", denied_open)
    monkeypatch.setattr(os, "access", denied_access)


@pytest.mark.parametrize("error", [errno.EROFS, errno.EACCES, errno.EPERM])
@pytest.mark.parametrize("existing", [False, True])
def test_readonly_home_hot_cache_and_cookie_import(readonly_home, monkeypatch, capsys, error, existing):
    home, temp = readonly_home
    original_cookie_dir = crawler_bridge.COOKIE_DIR
    if existing:
        for directory in (render.OUTPUT_DIR, cache.CACHE_DIR, original_cookie_dir):
            directory.mkdir(parents=True)
    block_home_writes(monkeypatch, home, error, existing)

    data = {"generated_at": "2026-11-17 12:00", "timezone": "Asia/Shanghai", "topic_filter": None,
            "boards": {"weibo": {"label": "微博热搜", "kind": "board", "items": [
                {"rank": 1, "title": "测试热榜", "url": "https://s.weibo.com/x"}]}}, "topics": []}
    monkeypatch.setattr(trending, "build", lambda *a, **kw: data)
    args = SimpleNamespace(hot_sources="weibo", hot_limit=10, hot_title="热榜", emit="html-path", save_dir=None)
    assert last30days._run_hot(args, "") == 0
    assert temp in render.OUTPUT_DIR.parents
    assert (render.OUTPUT_DIR / "hot.html").is_file()

    cache.save_cache("readonly", {"topic": "测试"})
    assert cache.load_cache("readonly") == {"topic": "测试"}
    cache.save_model_cache({"test": "model"})
    assert cache.load_model_cache() == {"test": "model"}
    assert temp in cache.MODEL_CACHE_FILE.parents

    assert last30days._run_login("xiaohongshu", "web_session=test-secret", 1) == 0
    fallback = Path(crawler_bridge.login_status("xiaohongshu")["cookie_dir"])
    assert temp in fallback.parents
    assert crawler_bridge.has_login("xiaohongshu")
    if os.name != "nt":
        assert fallback.stat().st_mode & 0o777 == 0o700
        for path in fallback.glob("*.json"):
            assert path.stat().st_mode & 0o777 == 0o600

    # The configured directory remains available for pre-existing sessions.
    assert crawler_bridge.COOKIE_DIR == original_cookie_dir
    assert crawler_bridge.has_login("xiaohongshu")
    status = crawler_bridge.get_crawler_status()
    assert status["cookie_dir"] == str(fallback)
    assert status["logins"]["xiaohongshu"]["login_method"] == "cookie-import"
    crawler_bridge.mark_logged_out("xiaohongshu")
    assert not crawler_bridge.has_login("xiaohongshu")
    captured = capsys.readouterr()
    assert "test-secret" not in captured.out + captured.err


def test_cookie_import_reports_unwritable_temp_without_traceback(readonly_home, monkeypatch, capsys):
    def denied(*args, **kwargs):
        raise OSError(errno.EROFS, "Read-only file system")

    monkeypatch.setattr(Path, "mkdir", denied)
    assert last30days._run_login("weibo", "SUB=test-secret", 1) == 1
    captured = capsys.readouterr()
    assert "LAST30DAYS_CN_CONFIG_DIR" in captured.err
    assert "test-secret" not in captured.err
    assert "已导入" not in captured.out


def test_cookie_fallback_is_reused_by_a_separate_command(tmp_path):
    # A file in place of the config parent also makes storage fail with OSError.
    blocked = tmp_path / "blocked"
    blocked.write_text("not a directory", encoding="utf-8")
    temp = tmp_path / "temp"
    temp.mkdir()
    config = str(blocked / "config")
    process_env = dict(os.environ, LAST30DAYS_CN_CONFIG_DIR=config,
                       TMPDIR=str(temp), TMP=str(temp), TEMP=str(temp))
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    imported = subprocess.run(
        [sys.executable, str(scripts / "last30days.py"), "login", "xiaohongshu", "--cookie", "web_session=test-secret"],
        env=process_env, capture_output=True, text=True, encoding="utf-8", timeout=15,
    )
    assert imported.returncode == 0, imported.stderr
    checked = subprocess.run(
        [sys.executable, "-c", "from lib import crawler_bridge as c; "
         "assert c.has_login('xiaohongshu'); "
         "assert c.login_status('xiaohongshu')['login_method'] == 'cookie-import'; "
         "assert 'xiaohongshu' in c.get_crawler_status()['cached_logins']"],
        cwd=str(scripts), env=process_env, capture_output=True, text=True, encoding="utf-8", timeout=15,
    )
    assert checked.returncode == 0, checked.stderr


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits and symlinks")
@pytest.mark.parametrize("unsafe", ["symlink", "shared"])
def test_cookie_fallback_rejects_unsafe_directory(readonly_home, monkeypatch, capsys, unsafe):
    home, temp = readonly_home
    fallback = crawler_bridge._cookie_fallback_dir()
    if unsafe == "symlink":
        target = temp / "target"
        target.mkdir(mode=0o700)
        fallback.symlink_to(target, target_is_directory=True)
    else:
        fallback.mkdir()
        fallback.chmod(0o755)
    block_home_writes(monkeypatch, home, errno.EROFS, False)
    assert last30days._run_login("weibo", "SUB=test-secret", 1) == 1
    assert not list(fallback.glob("*.json"))
    assert "test-secret" not in capsys.readouterr().err


def test_writable_environment_overrides_are_preserved(readonly_home, monkeypatch):
    home, temp = readonly_home
    monkeypatch.setenv("LAST30DAYS_OUTPUT_DIR", str(home / "custom-output"))
    monkeypatch.setenv("LAST30DAYS_CACHE_DIR", str(home / "custom-cache"))
    render.ensure_output_dir()
    cache.save_cache("custom", {"ok": True})
    assert render.OUTPUT_DIR == home / "custom-output"
    assert cache.CACHE_DIR == home / "custom-cache"
    assert cache.MODEL_CACHE_FILE == cache.CACHE_DIR / "model_selection.json"
    assert last30days._run_login("weibo", "SUB=test-secret", 1) == 0
    assert crawler_bridge.COOKIE_DIR == home / "config" / "browser_cookies"
    assert not list(temp.iterdir())


def test_fallback_preserves_existing_readonly_sessions(readonly_home, monkeypatch):
    home, temp = readonly_home
    crawler_bridge.import_cookie_header("weibo", "SUB=existing-secret")
    block_home_writes(monkeypatch, home, errno.EROFS, True)
    crawler_bridge.import_cookie_header("xiaohongshu", "web_session=new-secret")
    assert crawler_bridge.has_login("weibo")
    assert crawler_bridge.has_login("xiaohongshu")
    status = crawler_bridge.get_crawler_status()
    assert status["cached_logins"] == ["weibo", "xiaohongshu"]
    assert status["logins"]["weibo"]["cookie_dir"] == str(crawler_bridge.COOKIE_DIR)
    assert status["logins"]["xiaohongshu"]["cookie_dir"] != str(crawler_bridge.COOKIE_DIR)


def test_saved_cookies_are_readable_when_no_temp_directory_is_writable(readonly_home, monkeypatch):
    crawler_bridge.import_cookie_header("weibo", "SUB=existing-secret")

    def no_temp():
        raise FileNotFoundError("No usable temporary directory found")

    monkeypatch.setattr(crawler_bridge.tempfile, "gettempdir", no_temp)
    assert crawler_bridge.has_login("weibo")
