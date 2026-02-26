"""File operations: fingerprinting, backup, atomic write, locking."""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
import time
from datetime import datetime, timezone
from io import TextIOWrapper
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


class WorkbookLock:
    """Exclusive sidecar lock for workbook mutation.

    Uses a ``<file>.xl.lock`` sidecar next to the workbook to prevent
    concurrent mutations.  The lock is held for the entire read-modify-write
    cycle.

    On process crash the OS automatically releases the file lock.  The
    ``.xl.lock`` file may remain on disk but will be stale (unlocked), so
    the next process can acquire it normally.
    """

    def __init__(self, workbook_path: str | Path, *, timeout: float = 0) -> None:
        self.workbook_path = Path(workbook_path).resolve()
        self.timeout = timeout
        self._lock_path = self.workbook_path.parent / (self.workbook_path.name + ".xl.lock")
        self._lock_file: TextIOWrapper | None = None

    @property
    def lock_path(self) -> Path:
        return self._lock_path

    def __enter__(self) -> "WorkbookLock":
        self._lock_file = open(self._lock_path, "a+")  # noqa: SIM115
        try:
            if self.timeout <= 0:
                portalocker.lock(self._lock_file, portalocker.LOCK_EX | portalocker.LOCK_NB)
            else:
                deadline = time.monotonic() + self.timeout
                interval = min(0.1, max(0.01, self.timeout / 20))
                while True:
                    try:
                        portalocker.lock(self._lock_file, portalocker.LOCK_EX | portalocker.LOCK_NB)
                        break
                    except portalocker.LockException:
                        if time.monotonic() >= deadline:
                            raise
                        time.sleep(interval)
        except portalocker.LockException:
            if self._lock_file is not None:
                self._lock_file.close()
                self._lock_file = None
            raise

        # Write diagnostic info (PID + timestamp) for lock-status
        self._lock_file.seek(0)
        self._lock_file.truncate()
        self._lock_file.write(f"pid={os.getpid()}\n")
        self._lock_file.write(f"time={datetime.now(timezone.utc).isoformat()}\n")
        self._lock_file.flush()
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        if self._lock_file is not None:
            try:
                portalocker.unlock(self._lock_file)
            finally:
                self._lock_file.close()
                self._lock_file = None


def check_lock(path: str | Path) -> dict:
    """Best-effort check if a workbook is locked by xl CLI.

    Probes the sidecar ``.xl.lock`` file.  Returns a status dict with
    ``exists`` (whether the workbook file exists), ``locked``,
    ``lock_file``, and optional ``holder`` info.
    """
    path = Path(path).resolve()
    lock_path = path.parent / (path.name + ".xl.lock")
    wb_exists = path.exists()

    if not lock_path.exists():
        return {"exists": wb_exists, "locked": False, "lock_file": str(lock_path)}

    try:
        fd = open(lock_path, "a+")  # noqa: SIM115
        try:
            portalocker.lock(fd, portalocker.LOCK_EX | portalocker.LOCK_NB)
            portalocker.unlock(fd)
        finally:
            fd.close()
        return {"exists": wb_exists, "locked": False, "lock_file": str(lock_path)}
    except portalocker.LockException:
        holder: dict[str, str] = {}
        try:
            content = lock_path.read_text()
            for line in content.strip().splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    holder[k.strip()] = v.strip()
        except OSError:
            pass
        return {"exists": wb_exists, "locked": True, "lock_file": str(lock_path), "holder": holder}
    except OSError:
        return {"exists": wb_exists, "locked": False, "lock_file": str(lock_path), "check_error": True}


def read_text_safe(path: str | Path) -> str:
    """Read a text file with UTF-8 BOM tolerance.

    Uses ``utf-8-sig`` encoding which silently strips a leading BOM when
    present, while reading plain UTF-8 correctly.
    """
    return Path(path).read_text(encoding="utf-8-sig")
