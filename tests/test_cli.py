"""Tests for CLI commands via Typer test runner."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from xl.cli import app

runner = CliRunner()


def test_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert "version" in data["result"]


def test_wb_inspect(simple_workbook: Path):
    result = runner.invoke(app, ["wb", "inspect", "--file", str(simple_workbook)])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["command"] == "wb.inspect"
    assert len(data["result"]["sheets"]) == 2
    assert data["result"]["fingerprint"].startswith("sha256:")


def test_wb_inspect_not_found(tmp_path: Path):
    result = runner.invoke(app, ["wb", "inspect", "--file", str(tmp_path / "nope.xlsx")])
    data = json.loads(result.stdout)
    assert data["ok"] is False
    assert data["errors"][0]["code"] == "ERR_WORKBOOK_NOT_FOUND"


def test_sheet_ls(simple_workbook: Path):
    result = runner.invoke(app, ["sheet", "ls", "--file", str(simple_workbook)])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    names = [s["name"] for s in data["result"]]
    assert "Revenue" in names
    assert "Summary" in names


def test_table_ls(simple_workbook: Path):
    result = runner.invoke(app, ["table", "ls", "--file", str(simple_workbook)])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert len(data["result"]) == 1
    assert data["result"][0]["name"] == "Sales"


def test_table_ls_filter_sheet(simple_workbook: Path):
    result = runner.invoke(app, ["table", "ls", "--file", str(simple_workbook), "--sheet", "Summary"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["result"] == []


def test_table_add_column_dry_run(simple_workbook: Path):
    result = runner.invoke(app, [
        "table", "add-column",
        "--file", str(simple_workbook),
        "--table", "Sales",
        "--name", "Margin",
        "--formula", "=[@Sales]-[@Cost]",
        "--dry-run",
    ])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["result"]["dry_run"] is True
    assert len(data["changes"]) == 1
    assert data["changes"][0]["type"] == "table.add_column"


def test_table_add_column_apply(simple_workbook: Path):
    result = runner.invoke(app, [
        "table", "add-column",
        "--file", str(simple_workbook),
        "--table", "Sales",
        "--name", "Margin",
        "--formula", "=[@Sales]-[@Cost]",
    ])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["result"]["dry_run"] is False

    # Verify column persisted
    result = runner.invoke(app, ["table", "ls", "--file", str(simple_workbook)])
    data = json.loads(result.stdout)
    col_names = [c["name"] for c in data["result"][0]["columns"]]
    assert "Margin" in col_names


def test_table_append_rows(simple_workbook: Path):
    rows = json.dumps([
        {"Region": "Central", "Product": "Widget", "Sales": 1200, "Cost": 700},
    ])
    result = runner.invoke(app, [
        "table", "append-rows",
        "--file", str(simple_workbook),
        "--table", "Sales",
        "--data", rows,
    ])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["changes"][0]["after"]["rows_added"] == 1


def test_cell_set(simple_workbook: Path):
    result = runner.invoke(app, [
        "cell", "set",
        "--file", str(simple_workbook),
        "--ref", "Revenue!A2",
        "--value", "Updated",
    ])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["changes"][0]["after"] == "Updated"


def test_validate_workbook(simple_workbook: Path):
    result = runner.invoke(app, ["validate", "workbook", "--file", str(simple_workbook)])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["result"]["valid"] is True


def test_validate_plan(simple_workbook: Path, sample_plan_file: Path):
    result = runner.invoke(app, [
        "validate", "plan",
        "--file", str(simple_workbook),
        "--plan", str(sample_plan_file),
    ])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["result"]["valid"] is True


def test_plan_show(sample_plan_file: Path):
    result = runner.invoke(app, ["plan", "show", "--plan", str(sample_plan_file)])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["result"]["plan_id"] == "pln_test_001"


def test_plan_add_column(simple_workbook: Path):
    result = runner.invoke(app, [
        "plan", "add-column",
        "--file", str(simple_workbook),
        "--table", "Sales",
        "--name", "Margin",
        "--formula", "=[@Sales]-[@Cost]",
    ])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    plan = data["result"]
    assert plan["target"]["file"] == str(simple_workbook)
    assert len(plan["operations"]) == 1
    assert plan["operations"][0]["type"] == "table.add_column"


def test_apply_dry_run(simple_workbook: Path, sample_plan_file: Path):
    result = runner.invoke(app, [
        "apply",
        "--file", str(simple_workbook),
        "--plan", str(sample_plan_file),
        "--dry-run",
        "--no-backup",
    ])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["result"]["dry_run"] is True
    assert data["result"]["applied"] is False
    assert len(data["changes"]) == 1


def test_apply_with_backup(simple_workbook: Path, sample_plan_file: Path):
    result = runner.invoke(app, [
        "apply",
        "--file", str(simple_workbook),
        "--plan", str(sample_plan_file),
        "--backup",
    ])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["result"]["applied"] is True
    assert data["result"]["backup_path"] is not None
    assert Path(data["result"]["backup_path"]).exists()


def test_apply_fingerprint_conflict(simple_workbook: Path, tmp_path: Path):
    """Plan with wrong fingerprint should fail."""
    plan_data = {
        "schema_version": "1.0",
        "plan_id": "pln_conflict",
        "target": {
            "file": str(simple_workbook),
            "fingerprint": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
        },
        "options": {"fail_on_external_change": True},
        "operations": [],
    }
    plan_path = tmp_path / "bad_plan.json"
    plan_path.write_text(json.dumps(plan_data))

    result = runner.invoke(app, [
        "apply",
        "--file", str(simple_workbook),
        "--plan", str(plan_path),
    ])
    data = json.loads(result.stdout)
    assert data["ok"] is False
    assert "FINGERPRINT" in data["errors"][0]["code"]
