"""Structured logging, event emission, and trace support."""

from __future__ import annotations

import time
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
