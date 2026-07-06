"""回归测试：保证可安装的 SKILL 载荷入口是普通文件而非损坏的 symlink。

背景见 issue #10：skills/last30days/SKILL.md 曾被以 symlink 模式（120000）提交，
但 blob 内容是完整 SKILL 正文，导致 macOS/Linux clone 时报 "File name too long"。
"""

import os
import subprocess
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SKILL_ENTRY = os.path.join(REPO_ROOT, "skills", "last30days", "SKILL.md")


def test_skill_entry_is_regular_file_not_symlink():
    assert os.path.exists(SKILL_ENTRY), "skills/last30days/SKILL.md 缺失"
    assert not os.path.islink(SKILL_ENTRY), "SKILL.md 不应是 symlink（见 issue #10）"


def test_skill_entry_has_frontmatter():
    with open(SKILL_ENTRY, "r", encoding="utf-8") as f:
        content = f.read()
    assert content.strip(), "SKILL.md 不应为空"
    assert "name:" in content, "SKILL.md 应包含 Agent Skill frontmatter"


def test_skill_documents_output_contract_and_cache_flags():
    with open(os.path.join(REPO_ROOT, "SKILL.md"), "r", encoding="utf-8") as f:
        content = f.read()
    for needle in ("输出契约", "--refresh", "--no-cache", "setup", "查询类型"):
        assert needle in content


def test_payload_matches_root_sources():
    result = subprocess.run(
        [sys.executable, os.path.join(REPO_ROOT, "scripts", "build_payload.py"), "--check"],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert result.returncode == 0, result.stdout + result.stderr
