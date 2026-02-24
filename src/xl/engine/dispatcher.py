"""Command dispatch and response envelope helpers."""

from __future__ import annotations

import sys
from typing import Any

import orjson

from xl.contracts.common import (
    ErrorDetail,
    Metrics,
    RecalcInfo,
    ResponseEnvelope,
    Target,
)

# Exit code mapping
EXIT_CODES = {
    "success": 0,
    "validation": 10,
    "protection": 20,
    "formula": 30,
    "conflict": 40,
    "io": 50,
    "recalc": 60,
    "unsupported": 70,
    "internal": 90,
}


def success_envelope(
    command: str,
    result: Any,
    *,
    target: Target | None = None,
    changes: list | None = None,
    warnings: list | None = None,
    duration_ms: int = 0,
    recalc_mode: str = "cached",
) -> ResponseEnvelope:
    return ResponseEnvelope(
        ok=True,
        command=command,
        target=target or Target(),
        result=result,
        changes=changes or [],
        warnings=warnings or [],
        metrics=Metrics(duration_ms=duration_ms),
        recalc=RecalcInfo(mode=recalc_mode),
    )


def error_envelope(
    command: str,
    code: str,
    message: str,
    *,
    target: Target | None = None,
    details: dict | None = None,
    duration_ms: int = 0,
) -> ResponseEnvelope:
    return ResponseEnvelope(
        ok=False,
        command=command,
        target=target or Target(),
        errors=[ErrorDetail(code=code, message=message, details=details)],
        metrics=Metrics(duration_ms=duration_ms),
    )


def output_json(envelope: ResponseEnvelope) -> str:
    """Serialize envelope to JSON string using orjson."""
    data = envelope.model_dump(mode="json")
    return orjson.dumps(data, option=orjson.OPT_INDENT_2).decode()


def print_response(envelope: ResponseEnvelope) -> None:
    """Print response as JSON to stdout."""
    sys.stdout.write(output_json(envelope) + "\n")


def exit_code_for(envelope: ResponseEnvelope) -> int:
    """Determine exit code from envelope errors."""
    if envelope.ok:
        return 0
    if not envelope.errors:
        return EXIT_CODES["internal"]
    code = envelope.errors[0].code
    if "VALIDATION" in code or "SCHEMA" in code:
        return EXIT_CODES["validation"]
    if "PROTECTED" in code:
        return EXIT_CODES["protection"]
    if "FORMULA" in code:
        return EXIT_CODES["formula"]
    if "FINGERPRINT" in code or "CONFLICT" in code:
        return EXIT_CODES["conflict"]
    if "IO" in code or "LOCK" in code or "NOT_FOUND" in code:
        return EXIT_CODES["io"]
    if "RECALC" in code:
        return EXIT_CODES["recalc"]
    if "UNSUPPORTED" in code:
        return EXIT_CODES["unsupported"]
    return EXIT_CODES["internal"]
