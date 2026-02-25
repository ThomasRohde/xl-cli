"""Regression tests for fixes from REPORT.md."""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from typer.testing import CliRunner

from xl.cli import app
from xl.io.fileops import fingerprint

runner = CliRunner()


def _json(stdout: str) -> dict:
    return json.loads(stdout)


def test_formula_find_invalid_regex_returns_envelope(simple_workbook: Path):
    result = runner.invoke(
        app,
        ["formula", "find", "--file", str(simple_workbook), "--pattern", "["],
    )
    data = _json(result.stdout)
    assert result.exit_code == 10
    assert data["ok"] is False
    assert data["errors"][0]["code"] == "ERR_PATTERN_INVALID"


def test_table_add_column_duplicate_rejected(simple_workbook: Path):
    first = runner.invoke(
        app,
        [
            "table",
            "add-column",
            "--file",
            str(simple_workbook),
            "--table",
            "Sales",
            "--name",
            "Margin",
            "--formula",
            "=[@Sales]-[@Cost]",
        ],
    )
    assert first.exit_code == 0

    second = runner.invoke(
        app,
        [
            "table",
            "add-column",
            "--file",
            str(simple_workbook),
            "--table",
            "Sales",
            "--name",
            "Margin",
            "--formula",
            "=[@Sales]-[@Cost]",
        ],
    )
    data = _json(second.stdout)
    assert second.exit_code == 10
    assert data["ok"] is False
    assert data["errors"][0]["code"] == "ERR_COLUMN_EXISTS"


def test_formula_set_table_column_skips_header(simple_workbook: Path):
    add = runner.invoke(
        app,
        [
            "table",
            "add-column",
            "--file",
            str(simple_workbook),
            "--table",
            "Sales",
            "--name",
            "NewCalc",
            "--default",
            "0",
        ],
    )
    assert add.exit_code == 0

    set_formula = runner.invoke(
        app,
        [
            "formula",
            "set",
            "--file",
            str(simple_workbook),
            "--ref",
            "Sales[NewCalc]",
            "--formula",
            "=[@Sales]-[@Cost]",
            "--force-overwrite-values",
        ],
    )
    assert set_formula.exit_code == 0

    header = runner.invoke(app, ["cell", "get", "--file", str(simple_workbook), "--ref", "Revenue!E1"])
    body = runner.invoke(app, ["cell", "get", "--file", str(simple_workbook), "--ref", "Revenue!E2"])
    header_data = _json(header.stdout)
    body_data = _json(body.stdout)
    assert header_data["result"]["value"] == "NewCalc"
    assert body_data["result"]["formula"] == "=[@Sales]-[@Cost]"


def test_plan_validate_rejects_envelope_input(simple_workbook: Path, tmp_path: Path):
    envelope_plan = tmp_path / "envelope_plan.json"
    gen = runner.invoke(
        app,
        [
            "plan",
            "add-column",
            "--file",
            str(simple_workbook),
            "--table",
            "Sales",
            "--name",
            "EnvelopeCol",
            "--formula",
            "=[@Sales]-[@Cost]",
        ],
    )
    assert gen.exit_code == 0
    envelope_plan.write_text(gen.stdout)

    validate = runner.invoke(
        app,
        ["validate", "plan", "--file", str(simple_workbook), "--plan", str(envelope_plan)],
    )
    data = _json(validate.stdout)
    assert validate.exit_code == 10
    assert data["ok"] is False
    assert data["errors"][0]["code"] == "ERR_PLAN_INVALID"


def test_plan_append_writes_to_disk(simple_workbook: Path, tmp_path: Path):
    plan_file = tmp_path / "append_plan.json"
    add = runner.invoke(
        app,
        [
            "plan",
            "add-column",
            "--file",
            str(simple_workbook),
            "--table",
            "Sales",
            "--name",
            "Margin1",
            "--append",
            str(plan_file),
        ],
    )
    assert add.exit_code == 0
    assert plan_file.exists()
    p1 = json.loads(plan_file.read_text())
    assert len(p1["operations"]) == 1

    fmt = runner.invoke(
        app,
        [
            "plan",
            "format",
            "--file",
            str(simple_workbook),
            "--ref",
            "Sales[Sales]",
            "--style",
            "currency",
            "--append",
            str(plan_file),
        ],
    )
    assert fmt.exit_code == 0
    p2 = json.loads(plan_file.read_text())
    assert len(p2["operations"]) == 2


def test_verify_assert_supports_row_count_gte_and_value_alias(simple_workbook: Path):
    assertions = json.dumps(
        [
            {"type": "row_count.gte", "table": "Sales", "min_rows": 4},
            {"type": "cell.value_equals", "ref": "Revenue!A2", "value": "North"},
        ]
    )
    result = runner.invoke(
        app,
        ["verify", "assert", "--file", str(simple_workbook), "--assertions", assertions],
    )
    data = _json(result.stdout)
    assert result.exit_code == 0
    assert data["ok"] is True


def test_verify_assert_failure_exit_code_is_validation(simple_workbook: Path):
    assertions = json.dumps([{"type": "cell.value_equals", "ref": "Revenue!A2", "expected": "WRONG"}])
    result = runner.invoke(
        app,
        ["verify", "assert", "--file", str(simple_workbook), "--assertions", assertions],
    )
    data = _json(result.stdout)
    assert result.exit_code == 10
    assert data["ok"] is False
    assert data["errors"][0]["code"] == "ERR_ASSERTION_FAILED"


def test_validate_refs_invalid_returns_validation_error(simple_workbook: Path):
    result = runner.invoke(
        app,
        ["validate", "refs", "--file", str(simple_workbook), "--ref", "Missing!A1"],
    )
    data = _json(result.stdout)
    assert result.exit_code == 10
    assert data["ok"] is False
    assert data["errors"][0]["code"] == "ERR_RANGE_INVALID"


def test_format_freeze_mutually_exclusive_flags(simple_workbook: Path):
    result = runner.invoke(
        app,
        [
            "format",
            "freeze",
            "--file",
            str(simple_workbook),
            "--sheet",
            "Revenue",
            "--ref",
            "B2",
            "--unfreeze",
        ],
    )
    data = _json(result.stdout)
    assert result.exit_code == 10
    assert data["ok"] is False
    assert data["errors"][0]["code"] == "ERR_INVALID_ARGUMENT"


def test_format_width_rejects_non_letter_columns(simple_workbook: Path):
    result = runner.invoke(
        app,
        [
            "format",
            "width",
            "--file",
            str(simple_workbook),
            "--sheet",
            "Revenue",
            "--columns",
            "1,2",
            "--width",
            "10",
            "--dry-run",
        ],
    )
    data = _json(result.stdout)
    assert result.exit_code == 10
    assert data["ok"] is False
    assert data["errors"][0]["code"] == "ERR_RANGE_INVALID"


def test_range_clear_formats_only_preserves_cell_value(simple_workbook: Path):
    fmt = runner.invoke(
        app,
        [
            "format",
            "number",
            "--file",
            str(simple_workbook),
            "--ref",
            "Revenue!C2:C2",
            "--style",
            "currency",
        ],
    )
    assert fmt.exit_code == 0

    clear = runner.invoke(
        app,
        [
            "range",
            "clear",
            "--file",
            str(simple_workbook),
            "--ref",
            "Revenue!C2:C2",
            "--formats",
        ],
    )
    clear_data = _json(clear.stdout)
    assert clear.exit_code == 0
    assert clear_data["changes"][0]["after"]["contents"] is False
    assert clear_data["changes"][0]["after"]["formats"] is True

    cell = runner.invoke(app, ["cell", "get", "--file", str(simple_workbook), "--ref", "Revenue!C2"])
    cell_data = _json(cell.stdout)
    assert cell_data["result"]["value"] == 1000


def test_diff_compare_missing_sheet_is_validation_error(simple_workbook: Path):
    result = runner.invoke(
        app,
        [
            "diff",
            "compare",
            "--file-a",
            str(simple_workbook),
            "--file-b",
            str(simple_workbook),
            "--sheet",
            "Missing",
        ],
    )
    data = _json(result.stdout)
    assert result.exit_code == 10
    assert data["ok"] is False
    assert data["errors"][0]["code"] == "ERR_RANGE_INVALID"


def test_query_invalid_sql_returns_envelope(simple_workbook: Path):
    result = runner.invoke(
        app,
        ["query", "--file", str(simple_workbook), "--sql", "SELECT Missing FROM Sales"],
    )
    data = _json(result.stdout)
    assert result.exit_code == 90
    assert data["ok"] is False
    assert data["errors"][0]["code"] == "ERR_QUERY_FAILED"


def test_run_invalid_workflow_structure_does_not_mutate_file(simple_workbook: Path, tmp_path: Path):
    wf = tmp_path / "invalid_workflow.yaml"
    wf.write_text("foo: bar\n")

    before = fingerprint(simple_workbook)
    result = runner.invoke(app, ["run", "--workflow", str(wf), "--file", str(simple_workbook)])
    after = fingerprint(simple_workbook)
    data = _json(result.stdout)

    assert result.exit_code == 10
    assert data["ok"] is False
    assert data["errors"][0]["code"] == "ERR_WORKFLOW_INVALID"
    assert before == after


def test_run_empty_steps_rejected_without_mutation(simple_workbook: Path, tmp_path: Path):
    wf = tmp_path / "empty_steps.yaml"
    wf.write_text(yaml.safe_dump({"schema_version": "1.0", "target": {"file": str(simple_workbook)}, "steps": []}))

    before = fingerprint(simple_workbook)
    result = runner.invoke(app, ["run", "--workflow", str(wf), "--file", str(simple_workbook)])
    after = fingerprint(simple_workbook)
    data = _json(result.stdout)

    assert result.exit_code == 10
    assert data["ok"] is False
    assert data["errors"][0]["code"] == "ERR_WORKFLOW_INVALID"
    assert before == after


def test_run_non_mutating_workflow_does_not_save(simple_workbook: Path, tmp_path: Path):
    wf_path = tmp_path / "read_only.yaml"
    workflow = {
        "schema_version": "1.0",
        "name": "read_only",
        "target": {"file": str(simple_workbook)},
        "defaults": {"dry_run": False},
        "steps": [{"id": "list_tables", "run": "table.ls", "args": {}}],
    }
    wf_path.write_text(yaml.safe_dump(workflow))

    before = fingerprint(simple_workbook)
    result = runner.invoke(app, ["run", "--workflow", str(wf_path), "--file", str(simple_workbook)])
    after = fingerprint(simple_workbook)
    data = _json(result.stdout)

    assert result.exit_code == 0
    assert data["ok"] is True
    assert before == after
