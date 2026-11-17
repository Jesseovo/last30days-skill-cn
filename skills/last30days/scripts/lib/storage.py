"""Directory checks shared by output, cache and browser-session storage."""

import os
import stat
import tempfile
from pathlib import Path


def check_private_directory(path: Path) -> None:
    """Reject symlinks and shared/foreign directories before storing secrets."""
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode):
        raise PermissionError(f"Not a private directory: {path}")
    if os.name != "nt" and (info.st_uid != os.getuid() or info.st_mode & 0o077):
        raise PermissionError(f"Directory must be owned by the current user with mode 0700: {path}")


def ensure_writable_directory(path: Path, create: bool = True, private: bool = False) -> None:
    """Probe writes too: mkdir(exist_ok=True) succeeds on existing read-only dirs."""
    if create:
        path.mkdir(mode=0o700 if private else 0o777, parents=True, exist_ok=True)
    if private:
        check_private_directory(path)
    with tempfile.TemporaryFile(dir=str(path)):
        pass
