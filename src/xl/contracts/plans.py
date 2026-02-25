"""Patch plan models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Precondition(BaseModel):
    """A precondition that must hold before a plan can be applied."""

    type: str  # sheet_exists, table_exists, column_exists, ...
    sheet: str | None = None
    table: str | None = None
    column: str | None = None
    ref: str | None = None


class Postcondition(BaseModel):
    """A postcondition that should hold after a plan is applied."""

    type: str
    sheet: str | None = None
    table: str | None = None
    column: str | None = None
    ref: str | None = None
    expected: Any | None = None


class Operation(BaseModel):
    """A single operation within a patch plan."""

    op_id: str
    type: str  # table.add_column, table.append_rows, format.number, cell.set, ...
    # All remaining fields are operation-specific
    table: str | None = None
    sheet: str | None = None
    name: str | None = None
    formula: str | None = None
    value: Any | None = None
    ref: str | None = None
    style: str | None = None
    decimals: int | None = None
    values: list[Any] | None = None
    column: str | None = None
    columns: list[str] | None = None  # column headers for table.create
    position: str | None = None  # append (default)
    rows: list[dict[str, Any]] | None = None
    schema_mode: str | None = None  # strict, allow-missing-null, map-by-header
    cell_type: str | None = None  # number, text, bool, date
    force_overwrite_values: bool = False
    force_overwrite_formulas: bool = False
    fill_mode: str | None = None


class PlanOptions(BaseModel):
    """Options controlling how a plan is applied."""

    recalc_mode: str = "cached"
    backup: bool = True
    fail_on_external_change: bool = True


class PlanTarget(BaseModel):
    """Target workbook for a patch plan."""

    file: str
    fingerprint: str | None = None


class PatchPlan(BaseModel):
    """A patch plan describing intended changes to a workbook."""

    schema_version: str = "1.0"
    plan_id: str = ""
    target: PlanTarget
    options: PlanOptions = Field(default_factory=PlanOptions)
    preconditions: list[Precondition] = Field(default_factory=list)
    operations: list[Operation] = Field(default_factory=list)
    postconditions: list[Postcondition] = Field(default_factory=list)
