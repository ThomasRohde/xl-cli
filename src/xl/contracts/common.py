"""Common Pydantic models: response envelope, errors, warnings, metrics."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class WorkbookCorruptError(Exception):
    """Raised when a workbook file cannot be parsed."""


class Target(BaseModel):
    """Identifies the target workbook/sheet/range for a command."""

    file: str | None = None
    sheet: str | None = None
    table: str | None = None
    ref: str | None = None


class WarningDetail(BaseModel):
    """Structured warning."""

    code: str
    message: str
    path: str | None = None


class ErrorDetail(BaseModel):
    """Structured error."""

    code: str
    message: str
    details: dict[str, Any] | None = None


class Metrics(BaseModel):
    """Execution metrics."""

    duration_ms: int = 0


class RecalcInfo(BaseModel):
    """Recalculation mode information."""

    mode: str = "cached"
    performed: bool = False


class ChangeRecord(BaseModel):
    """Describes a single change made (or projected) by a mutating command."""

    op_id: str | None = None
    type: str
    target: str
    before: Any | None = None
    after: Any | None = None
    impact: dict[str, Any] | None = None
    warnings: list[WarningDetail] = Field(default_factory=list)


class ResponseEnvelope(BaseModel):
    """Standard response envelope returned by every command."""

    ok: bool = True
    command: str = ""
    target: Target = Field(default_factory=Target)
    result: Any = None
    changes: list[ChangeRecord] = Field(default_factory=list)
    warnings: list[WarningDetail] = Field(default_factory=list)
    errors: list[ErrorDetail] = Field(default_factory=list)
    metrics: Metrics = Field(default_factory=Metrics)
    recalc: RecalcInfo = Field(default_factory=RecalcInfo)
