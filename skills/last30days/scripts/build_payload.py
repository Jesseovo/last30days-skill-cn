#!/usr/bin/env python3
"""Mirror root skill sources into the installable Agent Skill payload."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / "skills" / "last30days"
SOURCE_SKILL = ROOT / "SKILL.md"
SOURCE_SCRIPTS = ROOT / "scripts"
PAYLOAD_SKILL = PAYLOAD / "SKILL.md"
PAYLOAD_SCRIPTS = PAYLOAD / "scripts"

IGNORED_DIRS = {"__pycache__", ".pytest_cache"}
IGNORED_SUFFIXES = {".pyc", ".pyo"}


def _iter_files(base: Path) -> Iterable[Path]:
    for path in sorted(base.rglob("*")):
        if not path.is_file():
            continue
        rel_parts = path.relative_to(base).parts
        if any(part in IGNORED_DIRS for part in rel_parts):
            continue
        if path.suffix in IGNORED_SUFFIXES:
            continue
        yield path


def _mapping() -> Dict[Path, Path]:
    mapping = {SOURCE_SKILL: PAYLOAD_SKILL}
    for src in _iter_files(SOURCE_SCRIPTS):
        mapping[src] = PAYLOAD_SCRIPTS / src.relative_to(SOURCE_SCRIPTS)
    return mapping


def _payload_files() -> Iterable[Path]:
    if not PAYLOAD.exists():
        return []
    return _iter_files(PAYLOAD)


def _diffs() -> Tuple[List[str], List[Path]]:
    mapping = _mapping()
    expected = set(mapping.values())
    diffs: List[str] = []

    for src, dst in mapping.items():
        if not dst.exists():
            diffs.append(f"missing: {dst.relative_to(ROOT)}")
            continue
        if src.read_bytes() != dst.read_bytes():
            diffs.append(f"changed: {dst.relative_to(ROOT)}")

    orphans = [path for path in _payload_files() if path not in expected]
    for orphan in orphans:
        diffs.append(f"orphan: {orphan.relative_to(ROOT)}")

    return diffs, orphans


def check() -> int:
    diffs, _ = _diffs()
    if not diffs:
        print("payload matches root sources")
        return 0
    print("payload drift detected:")
    for diff in diffs:
        print(f"  - {diff}")
    print("run: python scripts/build_payload.py")
    return 1


def sync() -> int:
    PAYLOAD.mkdir(parents=True, exist_ok=True)
    for src, dst in _mapping().items():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    _, orphans = _diffs()
    for orphan in orphans:
        orphan.unlink()

    for directory in sorted((p for p in PAYLOAD.rglob("*") if p.is_dir()), reverse=True):
        try:
            directory.rmdir()
        except OSError:
            pass

    print(f"payload synced: {PAYLOAD.relative_to(ROOT)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync root sources to skills/last30days payload")
    parser.add_argument("--check", action="store_true", help="check for drift without writing")
    args = parser.parse_args()
    return check() if args.check else sync()


if __name__ == "__main__":
    sys.exit(main())
