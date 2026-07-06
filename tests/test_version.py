"""Version consistency checks."""

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from lib import http, version


def _frontmatter_version(path: Path) -> str:
    content = path.read_text(encoding="utf-8")
    match = re.search(r'^version:\s*["\']?([^"\'\n]+)', content, re.MULTILINE)
    assert match, f"missing version in {path}"
    return match.group(1)


def test_skill_frontmatter_uses_display_version():
    assert _frontmatter_version(REPO_ROOT / "SKILL.md") == version.DISPLAY_VERSION


def test_json_manifests_use_single_version_source():
    gemini = json.loads((REPO_ROOT / "gemini-extension.json").read_text(encoding="utf-8"))
    plugin = json.loads((REPO_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    marketplace = json.loads((REPO_ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))

    assert gemini["version"] == version.DISPLAY_VERSION
    assert plugin["version"] == version.VERSION
    assert marketplace["plugins"][0]["version"] == version.VERSION


def test_http_user_agent_uses_version():
    assert f"/{version.VERSION} " in http.USER_AGENT
