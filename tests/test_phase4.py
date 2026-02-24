"""Tests for Phase 4: verify, diff, policy, lock-status."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from xl.cli import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# verify assert
# ---------------------------------------------------------------------------
def test_verify_column_exists(simple_workbook: Path):
    """Verify that a table column exists."""
    assertions = json.dumps([
        {"type": "table.column_exists", "table": "Sales", "column": "Region"},
    ])
    result = runner.invoke(app, [
        "verify", "assert",
        "--file", str(simple_workbook),
        "--assertions", assertions,
    ])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["result"]["passed"] is True


def test_verify_column_not_exists(simple_workbook: Path):
    """Column that doesn't exist should fail."""
    assertions = json.dumps([
        {"type": "table.column_exists", "table": "Sales", "column": "Nonexistent"},
    ])
    result = runner.invoke(app, [
        "verify", "assert",
        "--file", str(simple_workbook),
        "--assertions", assertions,
    ])
    data = json.loads(result.stdout)
    assert data["ok"] is False
    assert data["result"]["passed"] is False


def test_verify_row_count(simple_workbook: Path):
    """Verify table row count."""
    assertions = json.dumps([
        {"type": "table.row_count", "table": "Sales", "expected": 4},
    ])
    result = runner.invoke(app, [
        "verify", "assert",
        "--file", str(simple_workbook),
        "--assertions", assertions,
    ])
    data = json.loads(result.stdout)
    assert data["ok"] is True


def test_verify_cell_value(simple_workbook: Path):
    """Verify a specific cell value."""
    assertions = json.dumps([
        {"type": "cell.value_equals", "ref": "Revenue!A2", "expected": "North"},
    ])
    result = runner.invoke(app, [
        "verify", "assert",
        "--file", str(simple_workbook),
        "--assertions", assertions,
    ])
    data = json.loads(result.stdout)
    assert data["ok"] is True


def test_verify_cell_not_empty(simple_workbook: Path):
    assertions = json.dumps([
        {"type": "cell.not_empty", "ref": "Revenue!A2"},
    ])
    result = runner.invoke(app, [
        "verify", "assert",
        "--file", str(simple_workbook),
        "--assertions", assertions,
    ])
    data = json.loads(result.stdout)
    assert data["ok"] is True


def test_verify_cell_type(simple_workbook: Path):
    assertions = json.dumps([
        {"type": "cell.value_type", "ref": "Revenue!C2", "expected_type": "number"},
    ])
    result = runner.invoke(app, [
        "verify", "assert",
        "--file", str(simple_workbook),
        "--assertions", assertions,
    ])
    data = json.loads(result.stdout)
    assert data["ok"] is True


def test_verify_multiple_assertions(simple_workbook: Path):
    """Multiple assertions, some pass and some fail."""
    assertions = json.dumps([
        {"type": "cell.value_equals", "ref": "Revenue!A2", "expected": "North"},
        {"type": "cell.value_equals", "ref": "Revenue!A2", "expected": "Wrong"},
    ])
    result = runner.invoke(app, [
        "verify", "assert",
        "--file", str(simple_workbook),
        "--assertions", assertions,
    ])
    data = json.loads(result.stdout)
    assert data["ok"] is False
    assert data["result"]["passed_count"] == 1
    assert data["result"]["total"] == 2


def test_verify_from_file(simple_workbook: Path, tmp_path: Path):
    """Load assertions from file."""
    assertions = [
        {"type": "table.column_exists", "table": "Sales", "column": "Region"},
    ]
    af = tmp_path / "assertions.json"
    af.write_text(json.dumps(assertions))

    result = runner.invoke(app, [
        "verify", "assert",
        "--file", str(simple_workbook),
        "--assertions-file", str(af),
    ])
    data = json.loads(result.stdout)
    assert data["ok"] is True


# ---------------------------------------------------------------------------
# diff compare
# ---------------------------------------------------------------------------
def test_diff_identical(simple_workbook: Path, tmp_path: Path):
    """Diff of identical files should show no changes."""
    import shutil
    copy_path = tmp_path / "copy.xlsx"
    shutil.copy2(simple_workbook, copy_path)

    result = runner.invoke(app, [
        "diff", "compare",
        "--file-a", str(simple_workbook),
        "--file-b", str(copy_path),
    ])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["result"]["identical"] is True
    assert data["result"]["total_changes"] == 0


def test_diff_modified(simple_workbook: Path, tmp_path: Path):
    """Diff should detect modified cells."""
    import openpyxl
    import shutil
    copy_path = tmp_path / "modified.xlsx"
    shutil.copy2(simple_workbook, copy_path)

    # Modify a cell in the copy
    wb = openpyxl.load_workbook(str(copy_path))
    wb["Revenue"]["A2"] = "CHANGED"
    wb.save(str(copy_path))
    wb.close()

    result = runner.invoke(app, [
        "diff", "compare",
        "--file-a", str(simple_workbook),
        "--file-b", str(copy_path),
    ])
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["result"]["identical"] is False
    assert data["result"]["total_changes"] >= 1
    changes = data["result"]["cell_changes"]
    modified = [c for c in changes if c["ref"] == "Revenue!A2"]
    assert len(modified) == 1
    assert modified[0]["change_type"] == "modified"


# ---------------------------------------------------------------------------
# wb lock-status
# ---------------------------------------------------------------------------
def test_wb_lock_status(simple_workbook: Path):
    result = runner.invoke(app, [
        "wb", "lock-status",
        "--file", str(simple_workbook),
    ])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["result"]["locked"] is False
    assert data["result"]["exists"] is True


def test_wb_lock_status_nonexistent(tmp_path: Path):
    result = runner.invoke(app, [
        "wb", "lock-status",
        "--file", str(tmp_path / "nope.xlsx"),
    ])
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["result"]["exists"] is False


# ---------------------------------------------------------------------------
# Policy engine (unit tests)
# ---------------------------------------------------------------------------
def test_policy_load(tmp_path: Path):
    """Load a policy file."""
    from xl.validation.policy import Policy

    policy_data = """
protected_sheets:
  - Secret
mutation_thresholds:
  max_cells: 1000
  max_rows: 500
"""
    policy_path = tmp_path / "xl-policy.yaml"
    policy_path.write_text(policy_data)

    policy = Policy.load(policy_path)
    assert "Secret" in policy.protected_sheets
    assert policy.mutation_thresholds["max_cells"] == 1000


def test_policy_check_protected_sheet(tmp_path: Path):
    """Policy should flag operations targeting protected sheets."""
    from xl.contracts.plans import Operation, PatchPlan, PlanTarget
    from xl.validation.policy import Policy, check_plan_policy

    policy = Policy({"protected_sheets": ["Secret"], "protected_ranges": [], "mutation_thresholds": {}, "allowed_commands": [], "redaction": {}})
    plan = PatchPlan(
        plan_id="test",
        target=PlanTarget(file="test.xlsx"),
        operations=[
            Operation(op_id="op1", type="cell.set", sheet="Secret", ref="A1", value="hi"),
        ],
    )
    violations = check_plan_policy(policy, plan)
    assert len(violations) >= 1
    assert violations[0]["type"] == "protected_sheet"


def test_policy_check_mutation_threshold(tmp_path: Path):
    """Policy should flag plans exceeding mutation thresholds."""
    from xl.contracts.plans import Operation, PatchPlan, PlanTarget
    from xl.validation.policy import Policy, check_plan_policy

    policy = Policy({"protected_sheets": [], "protected_ranges": [], "mutation_thresholds": {"max_rows": 2}, "allowed_commands": [], "redaction": {}})
    plan = PatchPlan(
        plan_id="test",
        target=PlanTarget(file="test.xlsx"),
        operations=[
            Operation(op_id="op1", type="table.append_rows", table="T", rows=[{"a": 1}, {"a": 2}, {"a": 3}]),
        ],
    )
    violations = check_plan_policy(policy, plan)
    assert any(v["type"] == "mutation_threshold" for v in violations)
