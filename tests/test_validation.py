"""Tests for validation logic."""

from pathlib import Path

from xl.contracts.plans import (
    Operation,
    PatchPlan,
    PlanOptions,
    PlanTarget,
    Precondition,
)
from xl.engine.context import WorkbookContext
from xl.io.fileops import fingerprint
from xl.validation.validators import validate_plan, validate_workbook


def test_validate_workbook_clean(simple_workbook: Path):
    ctx = WorkbookContext(simple_workbook)
    result = validate_workbook(ctx)
    assert result.valid is True
    ctx.close()


def test_validate_plan_success(simple_workbook: Path):
    ctx = WorkbookContext(simple_workbook)
    fp = fingerprint(simple_workbook)
    plan = PatchPlan(
        plan_id="test",
        target=PlanTarget(file=str(simple_workbook), fingerprint=fp),
        preconditions=[Precondition(type="table_exists", table="Sales")],
        operations=[
            Operation(
                op_id="op1",
                type="table.add_column",
                table="Sales",
                name="NewCol",
            ),
        ],
    )
    result = validate_plan(ctx, plan)
    assert result.valid is True
    ctx.close()


def test_validate_plan_fingerprint_mismatch(simple_workbook: Path):
    ctx = WorkbookContext(simple_workbook)
    plan = PatchPlan(
        plan_id="test",
        target=PlanTarget(file=str(simple_workbook), fingerprint="sha256:wrong"),
        options=PlanOptions(fail_on_external_change=True),
        operations=[],
    )
    result = validate_plan(ctx, plan)
    assert result.valid is False
    failed = [c for c in result.checks if not c.get("passed")]
    assert any("fingerprint" in c.get("type", "").lower() for c in failed)
    ctx.close()


def test_validate_plan_missing_table(simple_workbook: Path):
    ctx = WorkbookContext(simple_workbook)
    fp = fingerprint(simple_workbook)
    plan = PatchPlan(
        plan_id="test",
        target=PlanTarget(file=str(simple_workbook), fingerprint=fp),
        preconditions=[Precondition(type="table_exists", table="NonExistent")],
        operations=[],
    )
    result = validate_plan(ctx, plan)
    assert result.valid is False
    ctx.close()


def test_validate_plan_column_already_exists(simple_workbook: Path):
    ctx = WorkbookContext(simple_workbook)
    fp = fingerprint(simple_workbook)
    plan = PatchPlan(
        plan_id="test",
        target=PlanTarget(file=str(simple_workbook), fingerprint=fp),
        operations=[
            Operation(
                op_id="op1",
                type="table.add_column",
                table="Sales",
                name="Region",  # Already exists
            ),
        ],
    )
    result = validate_plan(ctx, plan)
    assert result.valid is False
    ctx.close()


def test_validate_plan_table_create(simple_workbook: Path):
    """Validate a plan with table.create operation on a sheet with no overlap."""
    ctx = WorkbookContext(simple_workbook)
    fp = fingerprint(simple_workbook)
    plan = PatchPlan(
        plan_id="test",
        target=PlanTarget(file=str(simple_workbook), fingerprint=fp),
        preconditions=[Precondition(type="sheet_exists", sheet="Summary")],
        operations=[
            Operation(
                op_id="op1",
                type="table.create",
                table="NewTable",
                sheet="Summary",
                ref="A5:C8",
                columns=["X", "Y", "Z"],
            ),
        ],
    )
    result = validate_plan(ctx, plan)
    assert result.valid is True
    ctx.close()


def test_validate_plan_table_create_duplicate(simple_workbook: Path):
    """Validation should fail if table name already exists."""
    ctx = WorkbookContext(simple_workbook)
    fp = fingerprint(simple_workbook)
    plan = PatchPlan(
        plan_id="test",
        target=PlanTarget(file=str(simple_workbook), fingerprint=fp),
        operations=[
            Operation(
                op_id="op1",
                type="table.create",
                table="Sales",  # already exists
                sheet="Revenue",
                ref="F1:H3",
            ),
        ],
    )
    result = validate_plan(ctx, plan)
    assert result.valid is False
    ctx.close()
