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

VALIDATION_CODE_MARKERS = (
    "VALIDATION",
    "SCHEMA",
    "RANGE",
    "PLAN_INVALID",
    "MISSING_",
    "ASSERTION",
    "INVALID_ARGUMENT",
    "PATTERN_INVALID",
    "COLUMN_EXISTS",
    "WORKFLOW_INVALID",
    "USAGE",
    "TARGET_MISMATCH",
    "SHEET_NOT_FOUND",
    "SHEET_EXISTS",
)

IO_CODE_MARKERS = ("FILE_EXISTS",)


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


def summarize_changes(changes: list) -> dict:
    """Build a DryRunSummary dict from a list of ChangeRecord objects."""
    from xl.contracts.responses import DryRunSummary

    by_type: dict[str, int] = {}
    by_sheet: dict[str, int] = {}
    total_cells = 0
    ops: list[dict] = []

    for change in changes:
        # Accept both ChangeRecord objects and dicts
        if hasattr(change, "type"):
            c_type = change.type
            c_target = change.target
            c_impact = change.impact or {}
        else:
            c_type = change.get("type", "unknown")
            c_target = change.get("target", "")
            c_impact = change.get("impact") or {}

        by_type[c_type] = by_type.get(c_type, 0) + 1
        cells = c_impact.get("cells", 0) if isinstance(c_impact, dict) else 0
        total_cells += cells

        # Extract sheet name from target
        target_str = str(c_target)
        if "!" in target_str:
            sheet = target_str.split("!")[0]
        elif "[" in target_str:
            sheet = target_str.split("[")[0]
        else:
            sheet = target_str
        if sheet:
            by_sheet[sheet] = by_sheet.get(sheet, 0) + 1

        ops.append({"type": c_type, "target": target_str, "cells": cells})

    summary = DryRunSummary(
        total_operations=len(changes),
        total_cells_affected=total_cells,
        by_type=by_type,
        by_sheet=by_sheet,
        operations=ops,
    )
    return summary.model_dump()


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
    code = envelope.errors[0].code.upper()
    if "PROTECTED" in code:
        return EXIT_CODES["protection"]
    if "FORMULA" in code:
        return EXIT_CODES["formula"]
    if "FINGERPRINT" in code or "CONFLICT" in code:
        return EXIT_CODES["conflict"]
    if "UNSUPPORTED" in code:
        return EXIT_CODES["unsupported"]
    if any(marker in code for marker in VALIDATION_CODE_MARKERS):
        return EXIT_CODES["validation"]
    if any(marker in code for marker in IO_CODE_MARKERS):
        return EXIT_CODES["io"]
    if code.startswith("ERR_IO") or "LOCK" in code or code.endswith("NOT_FOUND") or "CORRUPT" in code:
        return EXIT_CODES["io"]
    if "RECALC" in code:
        return EXIT_CODES["recalc"]
    return EXIT_CODES["internal"]
