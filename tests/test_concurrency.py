"""Tests for WorkbookLock and concurrent file access safety."""

from __future__ import annotations

import json
import multiprocessing
import time
from pathlib import Path

import portalocker
import pytest

from xl.io.fileops import WorkbookLock, check_lock


# ---------------------------------------------------------------------------
# WorkbookLock unit tests
# ---------------------------------------------------------------------------


class TestWorkbookLock:
    """Unit tests for the WorkbookLock context manager."""

    def test_basic_acquire_release(self, simple_workbook: Path):
        """Lock can be acquired and released."""
        with WorkbookLock(simple_workbook):
            lock_path = simple_workbook.parent / (simple_workbook.name + ".xl.lock")
            assert lock_path.exists()
        # Lock released — re-acquire should succeed
        with WorkbookLock(simple_workbook):
            pass

    def test_lock_file_created(self, simple_workbook: Path):
        """Sidecar .xl.lock file is created on first acquisition."""
        lock_path = simple_workbook.parent / (simple_workbook.name + ".xl.lock")
        assert not lock_path.exists()
        with WorkbookLock(simple_workbook):
            assert lock_path.exists()
        # Lock file remains after release (by design)
        assert lock_path.exists()

    def test_lock_file_contains_pid(self, simple_workbook: Path):
        """Lock file contains diagnostic PID and timestamp."""
        import os

        lock_path = simple_workbook.parent / (simple_workbook.name + ".xl.lock")
        with WorkbookLock(simple_workbook):
            pass
        # Read after release — on Windows the exclusive lock blocks other handles
        content = lock_path.read_text()
        assert f"pid={os.getpid()}" in content
        assert "time=" in content

    def test_lock_path_property(self, simple_workbook: Path):
        lock = WorkbookLock(simple_workbook)
        expected = simple_workbook.parent / (simple_workbook.name + ".xl.lock")
        assert lock.lock_path == expected.resolve()

    def test_timeout_zero_fails_immediately(self, simple_workbook: Path):
        """With timeout=0, a second lock attempt fails immediately."""
        with WorkbookLock(simple_workbook):
            with pytest.raises(portalocker.LockException):
                # Use a fresh file handle in a subprocess to avoid
                # same-process handle sharing issues.
                _assert_lock_blocked(simple_workbook, timeout=0)


# ---------------------------------------------------------------------------
# check_lock() tests
# ---------------------------------------------------------------------------


class TestCheckLock:
    """Tests for the updated check_lock() that probes the sidecar."""

    def test_no_lock_file(self, simple_workbook: Path):
        """No sidecar file → not locked."""
        result = check_lock(simple_workbook)
        assert result["locked"] is False

    def test_stale_lock_file(self, simple_workbook: Path):
        """Stale (unlocked) sidecar file → not locked."""
        # Create then release a lock to leave a stale file
        with WorkbookLock(simple_workbook):
            pass
        result = check_lock(simple_workbook)
        assert result["locked"] is False

    def test_lock_file_key(self, simple_workbook: Path):
        """check_lock returns lock_file path."""
        result = check_lock(simple_workbook)
        assert "lock_file" in result


# ---------------------------------------------------------------------------
# Multiprocessing concurrency tests
# ---------------------------------------------------------------------------


def _hold_lock(workbook_path: str, ready_flag_path: str, done_flag_path: str):
    """Helper: acquire lock, signal ready, wait for done signal, release."""
    wb_path = Path(workbook_path)
    ready = Path(ready_flag_path)
    done = Path(done_flag_path)
    with WorkbookLock(wb_path, timeout=0):
        ready.write_text("ready")
        # Wait for test to signal completion
        for _ in range(100):
            if done.exists():
                break
            time.sleep(0.1)


def _assert_lock_blocked(workbook_path: Path, timeout: float = 0):
    """Try to acquire the lock; raises LockException if already held."""
    with WorkbookLock(workbook_path, timeout=timeout):
        pass  # Should not reach here if lock is held


def _try_lock_in_subprocess(workbook_path: str, timeout: float, result_path: str):
    """Subprocess helper: try to acquire lock, write result to file."""
    wb_path = Path(workbook_path)
    out = Path(result_path)
    try:
        with WorkbookLock(wb_path, timeout=timeout):
            out.write_text("acquired")
    except portalocker.LockException:
        out.write_text("blocked")
    except Exception as e:
        out.write_text(f"error:{e}")


def _short_hold(wb_path: str, ready_path: str, done_path: str):
    """Hold lock briefly, then release. Module-level for pickling on Windows."""
    with WorkbookLock(Path(wb_path), timeout=0):
        Path(ready_path).write_text("ready")
        time.sleep(0.5)  # Hold briefly


class TestConcurrentAccess:
    """Cross-process concurrency tests using multiprocessing."""

    def test_concurrent_lock_rejection(self, simple_workbook: Path, tmp_path: Path):
        """A second process cannot acquire the lock while the first holds it."""
        ready_flag = tmp_path / "ready.flag"
        done_flag = tmp_path / "done.flag"
        result_file = tmp_path / "result.txt"

        # Start holder process
        holder = multiprocessing.Process(
            target=_hold_lock,
            args=(str(simple_workbook), str(ready_flag), str(done_flag)),
        )
        holder.start()

        try:
            # Wait for holder to acquire lock
            for _ in range(50):
                if ready_flag.exists():
                    break
                time.sleep(0.1)
            assert ready_flag.exists(), "Holder process did not signal ready"

            # Try to acquire in another subprocess (should be blocked)
            contender = multiprocessing.Process(
                target=_try_lock_in_subprocess,
                args=(str(simple_workbook), 0, str(result_file)),
            )
            contender.start()
            contender.join(timeout=10)

            assert result_file.exists()
            assert result_file.read_text() == "blocked"
        finally:
            done_flag.write_text("done")
            holder.join(timeout=10)

    def test_lock_wait_success(self, simple_workbook: Path, tmp_path: Path):
        """A waiter succeeds after the holder releases within timeout."""
        ready_flag = tmp_path / "ready.flag"
        done_flag = tmp_path / "done.flag"
        result_file = tmp_path / "result.txt"

        holder = multiprocessing.Process(
            target=_short_hold,
            args=(str(simple_workbook), str(ready_flag), str(done_flag)),
        )
        holder.start()

        try:
            for _ in range(50):
                if ready_flag.exists():
                    break
                time.sleep(0.1)
            assert ready_flag.exists()

            # Try with a generous timeout — should succeed after holder releases
            contender = multiprocessing.Process(
                target=_try_lock_in_subprocess,
                args=(str(simple_workbook), 5, str(result_file)),
            )
            contender.start()
            contender.join(timeout=15)
            holder.join(timeout=10)

            assert result_file.exists()
            assert result_file.read_text() == "acquired"
        finally:
            done_flag.write_text("done")
            if holder.is_alive():
                holder.join(timeout=5)

    def test_lock_wait_timeout_expires(self, simple_workbook: Path, tmp_path: Path):
        """A waiter gets LockException when timeout expires."""
        ready_flag = tmp_path / "ready.flag"
        done_flag = tmp_path / "done.flag"
        result_file = tmp_path / "result.txt"

        holder = multiprocessing.Process(
            target=_hold_lock,
            args=(str(simple_workbook), str(ready_flag), str(done_flag)),
        )
        holder.start()

        try:
            for _ in range(50):
                if ready_flag.exists():
                    break
                time.sleep(0.1)
            assert ready_flag.exists()

            # Short timeout — holder won't release in time
            contender = multiprocessing.Process(
                target=_try_lock_in_subprocess,
                args=(str(simple_workbook), 0.3, str(result_file)),
            )
            contender.start()
            contender.join(timeout=10)

            assert result_file.exists()
            assert result_file.read_text() == "blocked"
        finally:
            done_flag.write_text("done")
            holder.join(timeout=10)


# ---------------------------------------------------------------------------
# CLI integration tests
# ---------------------------------------------------------------------------


def _cli_mutate_in_subprocess(workbook_path: str, result_path: str):
    """Run a mutating CLI command in a subprocess (without --wait-lock)."""
    from typer.testing import CliRunner
    from xl.cli import app

    runner = CliRunner()
    result = runner.invoke(app, [
        "cell", "set",
        "--file", workbook_path,
        "--ref", "Revenue!A2",
        "--value", "test_value",
        "--type", "text",
    ])
    Path(result_path).write_text(result.output)


class TestCLILocking:
    """CLI integration tests for lock behavior."""

    def test_mutating_command_creates_lock_file(self, simple_workbook: Path):
        """A mutating command creates and releases a sidecar lock file."""
        from typer.testing import CliRunner
        from xl.cli import app

        runner = CliRunner()
        result = runner.invoke(app, [
            "cell", "set",
            "--file", str(simple_workbook),
            "--ref", "Revenue!A2",
            "--value", "test",
            "--type", "text",
        ])
        data = json.loads(result.output)
        assert data["ok"] is True

        # Lock file should exist (stale) after command completes
        lock_path = simple_workbook.parent / (simple_workbook.name + ".xl.lock")
        assert lock_path.exists()

    def test_read_commands_unaffected_by_lock(self, simple_workbook: Path, tmp_path: Path):
        """Read-only commands succeed even when the lock is held."""
        from typer.testing import CliRunner
        from xl.cli import app

        ready_flag = tmp_path / "ready.flag"
        done_flag = tmp_path / "done.flag"

        holder = multiprocessing.Process(
            target=_hold_lock,
            args=(str(simple_workbook), str(ready_flag), str(done_flag)),
        )
        holder.start()

        try:
            for _ in range(50):
                if ready_flag.exists():
                    break
                time.sleep(0.1)
            assert ready_flag.exists()

            runner = CliRunner()
            # Read-only commands should succeed (they don't acquire locks)
            for cmd in [
                ["wb", "inspect", "--file", str(simple_workbook)],
                ["sheet", "ls", "--file", str(simple_workbook)],
                ["table", "ls", "--file", str(simple_workbook)],
            ]:
                result = runner.invoke(app, cmd)
                data = json.loads(result.output)
                assert data["ok"] is True, f"Command {cmd} failed: {result.output}"
        finally:
            done_flag.write_text("done")
            holder.join(timeout=10)

    def test_mutating_command_blocked_when_locked(self, simple_workbook: Path, tmp_path: Path):
        """A mutating CLI command emits ERR_LOCK_HELD when locked."""
        ready_flag = tmp_path / "ready.flag"
        done_flag = tmp_path / "done.flag"
        result_file = tmp_path / "cli_result.txt"

        holder = multiprocessing.Process(
            target=_hold_lock,
            args=(str(simple_workbook), str(ready_flag), str(done_flag)),
        )
        holder.start()

        try:
            for _ in range(50):
                if ready_flag.exists():
                    break
                time.sleep(0.1)
            assert ready_flag.exists()

            # Run CLI mutation in subprocess (will be blocked by lock)
            cli_proc = multiprocessing.Process(
                target=_cli_mutate_in_subprocess,
                args=(str(simple_workbook), str(result_file)),
            )
            cli_proc.start()
            cli_proc.join(timeout=10)

            assert result_file.exists()
            output = result_file.read_text()
            data = json.loads(output)
            assert data["ok"] is False
            assert any("ERR_LOCK_HELD" in e.get("code", "") for e in data.get("errors", []))
        finally:
            done_flag.write_text("done")
            holder.join(timeout=10)
