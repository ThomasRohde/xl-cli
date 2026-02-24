"""Tests for Pydantic contract models."""

from xl.contracts.common import (
    ChangeRecord,
    ErrorDetail,
    Metrics,
    RecalcInfo,
    ResponseEnvelope,
    Target,
    WarningDetail,
)
from xl.contracts.plans import Operation, PatchPlan, PlanTarget, Precondition
from xl.contracts.responses import SheetMeta, TableMeta, WorkbookMeta


def test_response_envelope_defaults():
    env = ResponseEnvelope()
    assert env.ok is True
    assert env.command == ""
    assert env.result is None
    assert env.changes == []
    assert env.warnings == []
    assert env.errors == []
    assert env.metrics.duration_ms == 0
    assert env.recalc.mode == "cached"


def test_response_envelope_roundtrip():
    env = ResponseEnvelope(
        ok=True,
        command="wb.inspect",
        target=Target(file="test.xlsx"),
        result={"key": "value"},
        metrics=Metrics(duration_ms=42),
    )
    data = env.model_dump()
    restored = ResponseEnvelope(**data)
    assert restored.command == "wb.inspect"
    assert restored.result == {"key": "value"}
    assert restored.metrics.duration_ms == 42


def test_patch_plan_model():
    plan = PatchPlan(
        plan_id="pln_test",
        target=PlanTarget(file="test.xlsx", fingerprint="sha256:abc"),
        preconditions=[Precondition(type="table_exists", table="Sales")],
        operations=[
            Operation(
                op_id="op1",
                type="table.add_column",
                table="Sales",
                name="Margin",
                formula="=[@Sales]-[@Cost]",
            )
        ],
    )
    assert plan.plan_id == "pln_test"
    assert len(plan.operations) == 1
    assert plan.operations[0].type == "table.add_column"


def test_workbook_meta_model():
    meta = WorkbookMeta(
        path="test.xlsx",
        fingerprint="sha256:abc",
        sheets=[SheetMeta(name="Sheet1", index=0)],
    )
    assert meta.has_macros is False
    assert len(meta.sheets) == 1
