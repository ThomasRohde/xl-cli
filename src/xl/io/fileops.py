"""File operations: fingerprinting, backup, atomic write, locking."""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import portalocker


def fingerprint(path: str | Path) -> str:
    """Compute SHA-256 fingerprint of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"


def backup(path: str | Path) -> str:
    """Create a timestamped backup of a file. Returns backup path."""
    path = Path(path)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_name = f"{path.stem}.{ts}.bak{path.suffix}"
    backup_path = path.parent / backup_name
    shutil.copy2(path, backup_path)
    return str(backup_path)


def atomic_write(target: str | Path, data: bytes) -> None:
    """Write data to target atomically via temp file + rename."""
    target = Path(target)
    fd, tmp_path = tempfile.mkstemp(
        dir=target.parent, suffix=target.suffix, prefix=".xl_tmp_"
    )
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        shutil.move(tmp_path, target)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def check_lock(path: str | Path) -> dict:
    """Best-effort check if a file is locked. Returns status dict."""
    path = Path(path)
    if not path.exists():
        return {"locked": False, "exists": False}
    try:
        with portalocker.Lock(str(path), mode="rb", timeout=0, flags=portalocker.LOCK_EX | portalocker.LOCK_NB):
            pass
        return {"locked": False, "exists": True}
    except portalocker.LockException:
        return {"locked": True, "exists": True}
    except OSError:
        return {"locked": False, "exists": True, "check_error": True}
