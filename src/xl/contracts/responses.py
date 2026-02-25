"""Command-specific result models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SheetMeta(BaseModel):
    """Metadata for a single worksheet."""

    name: str
    index: int
    visible: str = "visible"  # visible / hidden / veryHidden
    used_range: str | None = None
    table_count: int = 0


class NamedRangeMeta(BaseModel):
    """Metadata for a named range."""

    name: str
    scope: str = "workbook"  # workbook or sheet name
    ref: str = ""


class WorkbookMeta(BaseModel):
    """Metadata returned by ``wb inspect``."""

    path: str
    fingerprint: str
    sheets: list[SheetMeta] = Field(default_factory=list)
    names: list[NamedRangeMeta] = Field(default_factory=list)
    has_macros: bool = False
    has_external_links: bool = False
    unsupported_objects: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class TableColumnMeta(BaseModel):
    """Column within an Excel Table."""

    name: str
    index: int


class TableMeta(BaseModel):
    """Metadata for an Excel Table object."""

    table_id: str
    name: str
    sheet: str
    ref: str
    columns: list[TableColumnMeta] = Field(default_factory=list)
    style: str | None = None
    totals_row: bool = False
    row_count_estimate: int = 0


class ValidationResult(BaseModel):
    """Result of a validation command."""

    valid: bool = True
    checks: list[dict[str, Any]] = Field(default_factory=list)


class ApplyResult(BaseModel):
    """Result of an apply command."""

    applied: bool = False
    dry_run: bool = False
    backup_path: str | None = None
    operations_applied: int = 0
    fingerprint_before: str = ""
    fingerprint_after: str | None = None


class DryRunSummary(BaseModel):
    """Summary of changes projected during a dry-run."""

    total_operations: int = 0
    total_cells_affected: int = 0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_sheet: dict[str, int] = Field(default_factory=dict)
    operations: list[dict[str, Any]] = Field(default_factory=list)


class QueryResult(BaseModel):
    """Result of a query command."""

    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    row_count: int = 0
