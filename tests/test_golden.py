"""Golden workbook fixture tests — stable output validation.

These tests verify that CLI commands produce structurally correct and stable
JSON output against pre-built golden workbook fixtures. They protect against
regressions in the output contract.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from xl.cli import app

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "workbooks"
runner = CliRunner()


def _needs_golden(name: str) -> Path:
    path = FIXTURES_DIR / name
    if not path.exists():
        pytest.skip(f"Golden fixture not found: {name}")
    return path


# ---------------------------------------------------------------------------
# wb inspect — golden sales workbook
# ---------------------------------------------------------------------------
class TestGoldenWbInspect:
    def test_sales_inspect_structure(self, tmp_path: Path) -> None:
        src = _needs_golden("golden_sales.xlsx")
        wb = tmp_path / "sales.xlsx"
        shutil.copy2(src, wb)

        result = runner.invoke(app, ["wb", "inspect", "--file", str(wb)])
        assert result.exit_code == 0
        data = json.loads(result.stdout)

        assert data["ok"] is True
        assert data["command"] == "wb.inspect"
        meta = data["result"]
        assert meta["fingerprint"].startswith("sha256:")
        assert len(meta["sheets"]) == 2

        sheet_names = [s["name"] for s in meta["sheets"]]
        assert "Revenue" in sheet_names
        assert "Summary" in sheet_names

        assert meta["has_macros"] is False
        assert meta["has_external_links"] is False

    def test_empty_workbook_inspect(self, tmp_path: Path) -> None:
        src = _needs_golden("golden_empty.xlsx")
        wb = tmp_path / "empty.xlsx"
        shutil.copy2(src, wb)

        result = runner.invoke(app, ["wb", "inspect", "--file", str(wb)])
        assert result.exit_code == 0
        data = json.loads(result.stdout)

        assert data["ok"] is True
        meta = data["result"]
        assert len(meta["sheets"]) == 1
        assert meta["sheets"][0]["name"] == "Sheet1"

    def test_hidden_sheets_inspect(self, tmp_path: Path) -> None:
        src = _needs_golden("golden_hidden_sheets.xlsx")
        wb = tmp_path / "hidden.xlsx"
        shutil.copy2(src, wb)

        result = runner.invoke(app, ["wb", "inspect", "--file", str(wb)])
        assert result.exit_code == 0
        data = json.loads(result.stdout)

        assert data["ok"] is True
        meta = data["result"]
        sheets = {s["name"]: s["visible"] for s in meta["sheets"]}
        assert sheets["Visible"] == "visible"
        assert sheets["HiddenSheet"] == "hidden"
        assert sheets["VeryHidden"] == "veryHidden"


# ---------------------------------------------------------------------------
# sheet ls — golden workbooks
# ---------------------------------------------------------------------------
class TestGoldenSheetLs:
    def test_sales_sheet_ls(self, tmp_path: Path) -> None:
        src = _needs_golden("golden_sales.xlsx")
        wb = tmp_path / "sales.xlsx"
        shutil.copy2(src, wb)

        result = runner.invoke(app, ["sheet", "ls", "--file", str(wb)])
        assert result.exit_code == 0
        data = json.loads(result.stdout)

        assert data["ok"] is True
        sheets = data["result"]
        assert len(sheets) == 2
        assert sheets[0]["name"] == "Revenue"
        assert sheets[0]["index"] == 0
        assert sheets[1]["name"] == "Summary"
        assert sheets[1]["index"] == 1

    def test_hidden_sheets_ls(self, tmp_path: Path) -> None:
        src = _needs_golden("golden_hidden_sheets.xlsx")
        wb = tmp_path / "hidden.xlsx"
        shutil.copy2(src, wb)

        result = runner.invoke(app, ["sheet", "ls", "--file", str(wb)])
        assert result.exit_code == 0
        data = json.loads(result.stdout)

        sheets = data["result"]
        assert len(sheets) == 3
        hidden_count = sum(1 for s in sheets if s["visible"] != "visible")
        assert hidden_count == 2


# ---------------------------------------------------------------------------
# table ls — golden workbooks
# ---------------------------------------------------------------------------
class TestGoldenTableLs:
    def test_sales_table_ls(self, tmp_path: Path) -> None:
        src = _needs_golden("golden_sales.xlsx")
        wb = tmp_path / "sales.xlsx"
        shutil.copy2(src, wb)

        result = runner.invoke(app, ["table", "ls", "--file", str(wb)])
        assert result.exit_code == 0
        data = json.loads(result.stdout)

        assert data["ok"] is True
        tables = data["result"]
        assert len(tables) == 1

        t = tables[0]
        assert t["name"] == "Sales"
        assert t["sheet"] == "Revenue"
        col_names = [c["name"] for c in t["columns"]]
        assert col_names == ["Region", "Product", "Sales", "Cost"]
        assert t["row_count_estimate"] == 4

    def test_multi_table_ls(self, tmp_path: Path) -> None:
        src = _needs_golden("golden_multi_table.xlsx")
        wb = tmp_path / "multi.xlsx"
        shutil.copy2(src, wb)

        result = runner.invoke(app, ["table", "ls", "--file", str(wb)])
        assert result.exit_code == 0
        data = json.loads(result.stdout)

        tables = data["result"]
        assert len(tables) == 2
        names = sorted([t["name"] for t in tables])
        assert names == ["Orders", "Products"]

    def test_multi_table_filter_sheet(self, tmp_path: Path) -> None:
        src = _needs_golden("golden_multi_table.xlsx")
        wb = tmp_path / "multi.xlsx"
        shutil.copy2(src, wb)

        result = runner.invoke(app, ["table", "ls", "--file", str(wb), "--sheet", "Data"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data["result"]) == 2

    def test_empty_workbook_no_tables(self, tmp_path: Path) -> None:
        src = _needs_golden("golden_empty.xlsx")
        wb = tmp_path / "empty.xlsx"
        shutil.copy2(src, wb)

        result = runner.invoke(app, ["table", "ls", "--file", str(wb)])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["result"] == []


# ---------------------------------------------------------------------------
# validate workbook — golden workbooks
# ---------------------------------------------------------------------------
class TestGoldenValidate:
    def test_validate_clean_workbook(self, tmp_path: Path) -> None:
        src = _needs_golden("golden_sales.xlsx")
        wb = tmp_path / "sales.xlsx"
        shutil.copy2(src, wb)

        result = runner.invoke(app, ["validate", "workbook", "--file", str(wb)])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["ok"] is True
        assert data["result"]["valid"] is True

    def test_validate_hidden_sheets_workbook(self, tmp_path: Path) -> None:
        src = _needs_golden("golden_hidden_sheets.xlsx")
        wb = tmp_path / "hidden.xlsx"
        shutil.copy2(src, wb)

        result = runner.invoke(app, ["validate", "workbook", "--file", str(wb)])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["ok"] is True
        # Should detect hidden sheets
        checks = data["result"]["checks"]
        hidden_check = [c for c in checks if c.get("category") == "hidden_sheets"]
        assert len(hidden_check) == 1


# ---------------------------------------------------------------------------
# formula lint — golden formulas workbook
# ---------------------------------------------------------------------------
class TestGoldenFormulaLint:
    def test_lint_detects_volatile(self, tmp_path: Path) -> None:
        src = _needs_golden("golden_formulas.xlsx")
        wb = tmp_path / "formulas.xlsx"
        shutil.copy2(src, wb)

        result = runner.invoke(app, ["formula", "lint", "--file", str(wb)])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["ok"] is True

        findings = data["result"]["findings"]
        categories = [f["category"] for f in findings]
        assert "volatile_function" in categories

    def test_lint_detects_broken_ref(self, tmp_path: Path) -> None:
        src = _needs_golden("golden_formulas.xlsx")
        wb = tmp_path / "formulas.xlsx"
        shutil.copy2(src, wb)

        result = runner.invoke(app, ["formula", "lint", "--file", str(wb)])
        data = json.loads(result.stdout)
        findings = data["result"]["findings"]
        categories = [f["category"] for f in findings]
        assert "broken_ref" in categories


# ---------------------------------------------------------------------------
# formula find — golden formulas workbook
# ---------------------------------------------------------------------------
class TestGoldenFormulaFind:
    def test_find_vlookup(self, tmp_path: Path) -> None:
        src = _needs_golden("golden_formulas.xlsx")
        wb = tmp_path / "formulas.xlsx"
        shutil.copy2(src, wb)

        result = runner.invoke(app, ["formula", "find", "--file", str(wb), "--pattern", "VLOOKUP"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["ok"] is True
        matches = data["result"]["matches"]
        assert len(matches) >= 1
        assert "VLOOKUP" in matches[0]["match"]

    def test_find_sum(self, tmp_path: Path) -> None:
        src = _needs_golden("golden_formulas.xlsx")
        wb = tmp_path / "formulas.xlsx"
        shutil.copy2(src, wb)

        result = runner.invoke(app, ["formula", "find", "--file", str(wb), "--pattern", "SUM"])
        data = json.loads(result.stdout)
        assert data["ok"] is True
        assert len(data["result"]["matches"]) >= 1

    def test_find_no_match(self, tmp_path: Path) -> None:
        src = _needs_golden("golden_formulas.xlsx")
        wb = tmp_path / "formulas.xlsx"
        shutil.copy2(src, wb)

        result = runner.invoke(app, ["formula", "find", "--file", str(wb), "--pattern", "XYZNONEXISTENT"])
        data = json.loads(result.stdout)
        assert data["ok"] is True
        assert data["result"]["count"] == 0


# ---------------------------------------------------------------------------
# cell get — golden workbooks
# ---------------------------------------------------------------------------
class TestGoldenCellGet:
    def test_cell_get_text(self, tmp_path: Path) -> None:
        src = _needs_golden("golden_sales.xlsx")
        wb = tmp_path / "sales.xlsx"
        shutil.copy2(src, wb)

        result = runner.invoke(app, ["cell", "get", "--file", str(wb), "--ref", "Revenue!A1"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["ok"] is True
        assert data["result"]["value"] == "Region"
        assert data["result"]["type"] == "text"

    def test_cell_get_number(self, tmp_path: Path) -> None:
        src = _needs_golden("golden_sales.xlsx")
        wb = tmp_path / "sales.xlsx"
        shutil.copy2(src, wb)

        result = runner.invoke(app, ["cell", "get", "--file", str(wb), "--ref", "Revenue!C2"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["result"]["value"] == 1000
        assert data["result"]["type"] == "number"

    def test_cell_get_formula(self, tmp_path: Path) -> None:
        src = _needs_golden("golden_sales.xlsx")
        wb = tmp_path / "sales.xlsx"
        shutil.copy2(src, wb)

        result = runner.invoke(app, ["cell", "get", "--file", str(wb), "--ref", "Summary!B1"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["result"]["type"] == "formula"
        assert "SUM" in data["result"]["formula"]


# ---------------------------------------------------------------------------
# range stat — golden workbooks
# ---------------------------------------------------------------------------
class TestGoldenRangeStat:
    def test_range_stat_numeric(self, tmp_path: Path) -> None:
        src = _needs_golden("golden_sales.xlsx")
        wb = tmp_path / "sales.xlsx"
        shutil.copy2(src, wb)

        result = runner.invoke(app, ["range", "stat", "--file", str(wb), "--ref", "Revenue!C2:C5"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        stats = data["result"]
        assert stats["numeric_count"] == 4
        assert stats["sum"] == 5300
        assert stats["min"] == 800
        assert stats["max"] == 2000


# ---------------------------------------------------------------------------
# Envelope contract stability — every command returns valid envelope
# ---------------------------------------------------------------------------
class TestGoldenEnvelopeContract:
    """Verify that all commands return a properly structured ResponseEnvelope."""

    REQUIRED_KEYS = {"ok", "command", "target", "result", "changes", "warnings", "errors", "metrics", "recalc"}

    def _assert_envelope(self, stdout: str) -> dict:
        data = json.loads(stdout)
        missing = self.REQUIRED_KEYS - set(data.keys())
        assert not missing, f"Missing envelope keys: {missing}"
        assert isinstance(data["ok"], bool)
        assert isinstance(data["command"], str)
        assert isinstance(data["changes"], list)
        assert isinstance(data["warnings"], list)
        assert isinstance(data["errors"], list)
        assert "duration_ms" in data["metrics"]
        assert "mode" in data["recalc"]
        return data

    def test_wb_inspect_envelope(self, tmp_path: Path) -> None:
        src = _needs_golden("golden_sales.xlsx")
        wb = tmp_path / "sales.xlsx"
        shutil.copy2(src, wb)
        result = runner.invoke(app, ["wb", "inspect", "--file", str(wb)])
        assert result.exit_code == 0
        self._assert_envelope(result.stdout)

    def test_sheet_ls_envelope(self, tmp_path: Path) -> None:
        src = _needs_golden("golden_sales.xlsx")
        wb = tmp_path / "sales.xlsx"
        shutil.copy2(src, wb)
        result = runner.invoke(app, ["sheet", "ls", "--file", str(wb)])
        assert result.exit_code == 0
        self._assert_envelope(result.stdout)

    def test_table_ls_envelope(self, tmp_path: Path) -> None:
        src = _needs_golden("golden_sales.xlsx")
        wb = tmp_path / "sales.xlsx"
        shutil.copy2(src, wb)
        result = runner.invoke(app, ["table", "ls", "--file", str(wb)])
        assert result.exit_code == 0
        self._assert_envelope(result.stdout)

    def test_validate_workbook_envelope(self, tmp_path: Path) -> None:
        src = _needs_golden("golden_sales.xlsx")
        wb = tmp_path / "sales.xlsx"
        shutil.copy2(src, wb)
        result = runner.invoke(app, ["validate", "workbook", "--file", str(wb)])
        assert result.exit_code == 0
        self._assert_envelope(result.stdout)

    def test_cell_get_envelope(self, tmp_path: Path) -> None:
        src = _needs_golden("golden_sales.xlsx")
        wb = tmp_path / "sales.xlsx"
        shutil.copy2(src, wb)
        result = runner.invoke(app, ["cell", "get", "--file", str(wb), "--ref", "Revenue!A1"])
        assert result.exit_code == 0
        self._assert_envelope(result.stdout)

    def test_formula_lint_envelope(self, tmp_path: Path) -> None:
        src = _needs_golden("golden_formulas.xlsx")
        wb = tmp_path / "formulas.xlsx"
        shutil.copy2(src, wb)
        result = runner.invoke(app, ["formula", "lint", "--file", str(wb)])
        assert result.exit_code == 0
        self._assert_envelope(result.stdout)

    def test_error_envelope(self) -> None:
        result = runner.invoke(app, ["wb", "inspect", "--file", "/nonexistent/path.xlsx"])
        data = json.loads(result.stdout)
        self._assert_envelope(result.stdout)
        assert data["ok"] is False
        assert len(data["errors"]) > 0
        err = data["errors"][0]
        assert "code" in err
        assert "message" in err


# ---------------------------------------------------------------------------
# Mutation round-trip — add column, save, re-read
# ---------------------------------------------------------------------------
class TestGoldenMutationRoundtrip:
    def test_add_column_roundtrip(self, tmp_path: Path) -> None:
        """Add a column, then verify the workbook has it."""
        src = _needs_golden("golden_sales.xlsx")
        wb = tmp_path / "sales.xlsx"
        shutil.copy2(src, wb)

        # Add column
        result = runner.invoke(app, [
            "table", "add-column",
            "--file", str(wb),
            "--table", "Sales",
            "--name", "Margin",
            "--formula", "=[@Sales]-[@Cost]",
        ])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["ok"] is True

        # Re-inspect tables
        result = runner.invoke(app, ["table", "ls", "--file", str(wb)])
        data = json.loads(result.stdout)
        tables = data["result"]
        cols = [c["name"] for c in tables[0]["columns"]]
        assert "Margin" in cols

    def test_append_rows_roundtrip(self, tmp_path: Path) -> None:
        """Append rows, then verify row count increased."""
        src = _needs_golden("golden_sales.xlsx")
        wb = tmp_path / "sales.xlsx"
        shutil.copy2(src, wb)

        rows_json = json.dumps([
            {"Region": "Central", "Product": "Widget", "Sales": 1200, "Cost": 700},
        ])
        result = runner.invoke(app, [
            "table", "append-rows",
            "--file", str(wb),
            "--table", "Sales",
            "--data", rows_json,
        ])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["ok"] is True

        # Re-inspect
        result = runner.invoke(app, ["table", "ls", "--file", str(wb)])
        data = json.loads(result.stdout)
        assert data["result"][0]["row_count_estimate"] == 5

    def test_cell_set_roundtrip(self, tmp_path: Path) -> None:
        """Set a cell, then read it back."""
        src = _needs_golden("golden_sales.xlsx")
        wb = tmp_path / "sales.xlsx"
        shutil.copy2(src, wb)

        result = runner.invoke(app, [
            "cell", "set",
            "--file", str(wb),
            "--ref", "Summary!A2",
            "--value", "test_value",
        ])
        assert result.exit_code == 0

        result = runner.invoke(app, [
            "cell", "get",
            "--file", str(wb),
            "--ref", "Summary!A2",
        ])
        data = json.loads(result.stdout)
        assert data["result"]["value"] == "test_value"


# ---------------------------------------------------------------------------
# Diff golden workbooks
# ---------------------------------------------------------------------------
class TestGoldenDiff:
    def test_diff_identical(self, tmp_path: Path) -> None:
        src = _needs_golden("golden_sales.xlsx")
        a = tmp_path / "a.xlsx"
        b = tmp_path / "b.xlsx"
        shutil.copy2(src, a)
        shutil.copy2(src, b)

        result = runner.invoke(app, ["diff", "compare", "--file-a", str(a), "--file-b", str(b)])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["ok"] is True
        assert data["result"]["identical"] is True
        assert data["result"]["total_changes"] == 0

    def test_diff_after_mutation(self, tmp_path: Path) -> None:
        src = _needs_golden("golden_sales.xlsx")
        a = tmp_path / "a.xlsx"
        b = tmp_path / "b.xlsx"
        shutil.copy2(src, a)
        shutil.copy2(src, b)

        # Mutate b
        runner.invoke(app, [
            "cell", "set", "--file", str(b),
            "--ref", "Revenue!C2", "--value", "9999", "--type", "number",
        ])

        result = runner.invoke(app, ["diff", "compare", "--file-a", str(a), "--file-b", str(b)])
        data = json.loads(result.stdout)
        assert data["ok"] is True
        assert data["result"]["identical"] is False
        assert data["result"]["total_changes"] >= 1
