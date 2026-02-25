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


def test_plan_validate_accepts_envelope_input(simple_workbook: Path, tmp_path: Path):
    """Envelope files are auto-unwrapped: validate extracts .result as the plan body."""
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
    assert validate.exit_code == 0
    assert data["ok"] is True


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


# ---------------------------------------------------------------------------
# Finding 1: UTF-8 BOM tolerance
# ---------------------------------------------------------------------------

def test_load_plan_with_utf8_bom(simple_workbook: Path, sample_plan: dict, tmp_path: Path):
    """Plan JSON files with a UTF-8 BOM should parse without error."""
    plan_path = tmp_path / "bom_plan.json"
    bom = b"\xef\xbb\xbf"
    plan_path.write_bytes(bom + json.dumps(sample_plan).encode("utf-8"))

    result = runner.invoke(
        app,
        ["validate", "plan", "--file", str(simple_workbook), "--plan", str(plan_path)],
    )
    data = _json(result.stdout)
    assert data["ok"] is True


def test_workflow_yaml_with_utf8_bom(simple_workbook: Path, tmp_path: Path):
    """Workflow YAML files with a UTF-8 BOM should load correctly."""
    workflow = {
        "schema_version": "1.0",
        "name": "bom_test",
        "target": {"file": str(simple_workbook)},
        "steps": [{"id": "s1", "run": "wb.inspect", "args": {}}],
    }
    wf_path = tmp_path / "bom_workflow.yaml"
    bom = b"\xef\xbb\xbf"
    wf_path.write_bytes(bom + yaml.safe_dump(workflow).encode("utf-8"))

    result = runner.invoke(
        app, ["run", "--workflow", str(wf_path), "--file", str(simple_workbook)]
    )
    data = _json(result.stdout)
    assert data["ok"] is True


def test_assertions_file_with_utf8_bom(simple_workbook: Path, tmp_path: Path):
    """Assertions JSON files with a UTF-8 BOM should parse without error."""
    assertions = [{"type": "table.column_exists", "table": "Sales", "column": "Region"}]
    af = tmp_path / "bom_assertions.json"
    bom = b"\xef\xbb\xbf"
    af.write_bytes(bom + json.dumps(assertions).encode("utf-8"))

    result = runner.invoke(
        app,
        ["verify", "assert", "--file", str(simple_workbook), "--assertions-file", str(af)],
    )
    data = _json(result.stdout)
    assert data["ok"] is True


def test_data_file_with_utf8_bom(simple_workbook: Path, tmp_path: Path):
    """--data-file JSON with a UTF-8 BOM should parse without error."""
    rows = [{"Region": "Central", "Product": "Widget", "Sales": 500, "Cost": 300}]
    df = tmp_path / "bom_rows.json"
    bom = b"\xef\xbb\xbf"
    df.write_bytes(bom + json.dumps(rows).encode("utf-8"))

    result = runner.invoke(
        app,
        [
            "table", "append-rows",
            "--file", str(simple_workbook),
            "--table", "Sales",
            "--data-file", str(df),
        ],
    )
    data = _json(result.stdout)
    assert data["ok"] is True


# ---------------------------------------------------------------------------
# Finding 5: WARN_UNCACHED_FORMULA on cell get --data-only
# ---------------------------------------------------------------------------

def test_cell_get_data_only_warns_on_uncached_formula(simple_workbook: Path):
    """When --data-only returns null for a formula cell, a warning should appear."""
    result = runner.invoke(
        app,
        ["cell", "get", "--file", str(simple_workbook), "--ref", "Summary!B1", "--data-only"],
    )
    data = _json(result.stdout)
    assert data["ok"] is True
    # If the value is None (no cached value), we expect the warning
    if data["result"]["value"] is None:
        assert any(w["code"] == "WARN_UNCACHED_FORMULA" for w in data.get("warnings", []))


# ---------------------------------------------------------------------------
# Finding 6: diff compare --include-formulas
# ---------------------------------------------------------------------------

def test_diff_compare_include_formulas(simple_workbook: Path, tmp_path: Path):
    """diff compare --include-formulas should report formula text changes."""
    import shutil
    import openpyxl as oxl

    copy_path = tmp_path / "modified.xlsx"
    shutil.copy2(simple_workbook, copy_path)
    wb = oxl.load_workbook(str(copy_path))
    wb["Summary"]["B1"] = "=SUM(Revenue!C2:C4)"  # changed range
    wb.save(str(copy_path))
    wb.close()

    result = runner.invoke(
        app,
        [
            "diff", "compare",
            "--file-a", str(simple_workbook),
            "--file-b", str(copy_path),
            "--include-formulas",
        ],
    )
    data = _json(result.stdout)
    assert data["ok"] is True
    assert "formula_changes" in data["result"]
    assert len(data["result"]["formula_changes"]) > 0
    fc = data["result"]["formula_changes"][0]
    assert fc["change_type"] == "formula_modified"


# ---------------------------------------------------------------------------
# Finding 3: Workflow dispatcher expansion
# ---------------------------------------------------------------------------

def test_workflow_query_step(simple_workbook: Path, tmp_path: Path):
    """Workflow query step should execute SQL against tables."""
    workflow = {
        "schema_version": "1.0",
        "name": "query_test",
        "target": {"file": str(simple_workbook)},
        "steps": [{"id": "q1", "run": "query", "args": {"sql": "SELECT COUNT(*) as cnt FROM Sales"}}],
    }
    wf_path = tmp_path / "workflow_query.yaml"
    wf_path.write_text(yaml.safe_dump(workflow))

    result = runner.invoke(app, ["run", "--workflow", str(wf_path), "--file", str(simple_workbook)])
    data = _json(result.stdout)
    assert data["ok"] is True
    assert data["result"]["steps"][0]["ok"] is True
    assert data["result"]["steps"][0]["result"]["row_count"] == 1


def test_workflow_cell_get_step(simple_workbook: Path, tmp_path: Path):
    """Workflow cell.get step should read a cell value."""
    workflow = {
        "schema_version": "1.0",
        "name": "cell_get_test",
        "target": {"file": str(simple_workbook)},
        "steps": [{"id": "r1", "run": "cell.get", "args": {"ref": "Revenue!A2"}}],
    }
    wf_path = tmp_path / "workflow_cell_get.yaml"
    wf_path.write_text(yaml.safe_dump(workflow))

    result = runner.invoke(app, ["run", "--workflow", str(wf_path), "--file", str(simple_workbook)])
    data = _json(result.stdout)
    assert data["ok"] is True
    assert data["result"]["steps"][0]["result"]["value"] == "North"


def test_workflow_formula_find_step(simple_workbook: Path, tmp_path: Path):
    """Workflow formula.find step should find formulas matching a pattern."""
    workflow = {
        "schema_version": "1.0",
        "name": "ff_test",
        "target": {"file": str(simple_workbook)},
        "steps": [{"id": "f1", "run": "formula.find", "args": {"pattern": "SUM"}}],
    }
    wf_path = tmp_path / "workflow_ff.yaml"
    wf_path.write_text(yaml.safe_dump(workflow))

    result = runner.invoke(app, ["run", "--workflow", str(wf_path), "--file", str(simple_workbook)])
    data = _json(result.stdout)
    assert data["ok"] is True
    assert data["result"]["steps"][0]["ok"] is True


def test_workflow_invalid_step_rejected_at_parse_time(simple_workbook: Path, tmp_path: Path):
    """Workflow with unknown step command should fail at parse time."""
    workflow = {
        "schema_version": "1.0",
        "name": "bad_step",
        "target": {"file": str(simple_workbook)},
        "steps": [{"id": "s1", "run": "nonexistent.command", "args": {}}],
    }
    wf_path = tmp_path / "bad_step.yaml"
    wf_path.write_text(yaml.safe_dump(workflow))

    result = runner.invoke(app, ["run", "--workflow", str(wf_path), "--file", str(simple_workbook)])
    data = _json(result.stdout)
    assert data["ok"] is False
    assert data["errors"][0]["code"] == "ERR_WORKFLOW_INVALID"


# ---------------------------------------------------------------------------
# REPORT.md blind-test regression fixes
# ---------------------------------------------------------------------------


def test_verify_cell_value_type_accepts_expected_alias(simple_workbook: Path):
    """§4.7 — cell.value_type should accept 'expected' as alias for 'expected_type'."""
    assertions = json.dumps([
        {"type": "cell.value_type", "ref": "Revenue!C2", "expected": "number"},
    ])
    result = runner.invoke(
        app,
        ["verify", "assert", "--file", str(simple_workbook), "--assertions", assertions],
    )
    data = _json(result.stdout)
    assert result.exit_code == 0
    assert data["ok"] is True
    assert data["result"]["assertions"][0]["passed"] is True


def test_workflow_cell_set_with_type_arg(simple_workbook: Path, tmp_path: Path):
    """§4.3 — Workflow cell.set should accept 'type' arg for coercion."""
    wf_path = tmp_path / "wf_cell_type.yaml"
    workflow = {
        "schema_version": "1.0",
        "name": "cell_type_test",
        "target": {"file": str(simple_workbook)},
        "steps": [
            {"id": "s1", "run": "cell.set", "args": {"ref": "Summary!C1", "value": "42", "type": "number"}},
        ],
    }
    wf_path.write_text(yaml.safe_dump(workflow))

    result = runner.invoke(app, ["run", "--workflow", str(wf_path), "--file", str(simple_workbook)])
    data = _json(result.stdout)
    assert data["ok"] is True

    get_result = runner.invoke(app, ["cell", "get", "--file", str(simple_workbook), "--ref", "Summary!C1"])
    get_data = _json(get_result.stdout)
    assert get_data["result"]["value"] == 42
    assert get_data["result"]["type"] == "number"


def test_workflow_format_width_comma_separated_columns(simple_workbook: Path, tmp_path: Path):
    """§4.2 — Workflow format.width should accept columns as comma-separated string."""
    wf_path = tmp_path / "wf_width.yaml"
    workflow = {
        "schema_version": "1.0",
        "name": "width_test",
        "target": {"file": str(simple_workbook)},
        "steps": [
            {"id": "s1", "run": "format.width", "args": {"sheet": "Revenue", "columns": "A,B", "width": 20}},
        ],
    }
    wf_path.write_text(yaml.safe_dump(workflow))

    result = runner.invoke(app, ["run", "--workflow", str(wf_path), "--file", str(simple_workbook)])
    data = _json(result.stdout)
    assert data["ok"] is True
    assert data["result"]["steps"][0]["ok"] is True


def test_formula_set_range_defaults_to_relative(simple_workbook: Path):
    """§4.1 — Range formula set without --fill-mode should default to relative."""
    import openpyxl

    result = runner.invoke(app, [
        "formula", "set",
        "--file", str(simple_workbook),
        "--ref", "Revenue!E2:E5",
        "--formula", "=C2*D2",
        # No --fill-mode flag: should default to relative
    ])
    assert result.exit_code == 0
    data = _json(result.stdout)
    assert data["ok"] is True

    wb = openpyxl.load_workbook(str(simple_workbook))
    ws = wb["Revenue"]
    assert ws["E2"].value == "=C2*D2"
    assert ws["E3"].value == "=C3*D3"
    assert ws["E4"].value == "=C4*D4"
    assert ws["E5"].value == "=C5*D5"
    wb.close()
