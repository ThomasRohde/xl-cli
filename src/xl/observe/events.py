"""Structured logging, event emission, and trace support."""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class Timer:
    """Simple context-manager timer for measuring duration_ms."""

    def __init__(self) -> None:
        self.start: float = 0
        self.elapsed_ms: int = 0

    def __enter__(self) -> "Timer":
        self.start = time.perf_counter()
        return self

    def __exit__(self, *args: Any) -> None:
        self.elapsed_ms = int((time.perf_counter() - self.start) * 1000)


class EventEmitter:
    """Emits NDJSON lifecycle events to stderr."""

    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled

    def emit(self, event: str, data: dict[str, Any] | None = None) -> None:
        if not self.enabled:
            return
        payload = {
            "event": event,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data or {},
        }
        sys.stderr.write(json.dumps(payload) + "\n")
        sys.stderr.flush()


class TraceRecorder:
    """Records trace data during command execution."""

    def __init__(self) -> None:
        self.entries: list[dict[str, Any]] = []
        self._start = time.perf_counter()

    def record(self, category: str, data: dict[str, Any]) -> None:
        elapsed = int((time.perf_counter() - self._start) * 1000)
        self.entries.append({
            "category": category,
            "timestamp_ms": elapsed,
            **data,
        })

    def save(self, path: str | Path) -> str:
        """Save trace to a JSON file. Returns the path."""
        trace_path = Path(path)
        trace_data = {
            "trace_version": "1.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_duration_ms": int((time.perf_counter() - self._start) * 1000),
            "entries": self.entries,
        }
        trace_path.write_text(json.dumps(trace_data, indent=2, default=str))
        return str(trace_path)
