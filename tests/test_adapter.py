"""Tests for openpyxl_engine adapter operations."""

from pathlib import Path

import pytest

from xl.adapters.openpyxl_engine import (
    cell_set,
    format_number,
    table_add_column,
    table_append_rows,
)
from xl.engine.context import WorkbookContext


def test_table_add_column(simple_workbook: Path):
    ctx = WorkbookContext(simple_workbook)
    change = table_add_column(ctx, "Sales", "Margin", formula="=[@Sales]-[@Cost]")
    assert change.type == "table.add_column"
    assert "Margin" in change.target

    # Verify column was added
    tables = ctx.list_tables()
    col_names = [c.name for c in tables[0].columns]
    assert "Margin" in col_names
    ctx.close()


def test_table_add_column_not_found(simple_workbook: Path):
    ctx = WorkbookContext(simple_workbook)
    with pytest.raises(ValueError, match="Table not found"):
        table_add_column(ctx, "NonExistent", "Col")
    ctx.close()


def test_table_add_column_with_default(simple_workbook: Path):
    ctx = WorkbookContext(simple_workbook)
    change = table_add_column(ctx, "Sales", "Status", default_value="Active")
    assert change.type == "table.add_column"

    # Verify values
    ws = ctx.wb["Revenue"]
    # Header should be at col E (5th column), row 1
    assert ws.cell(row=1, column=5).value == "Status"
    assert ws.cell(row=2, column=5).value == "Active"
    ctx.close()


def test_table_append_rows(simple_workbook: Path):
    ctx = WorkbookContext(simple_workbook)
    rows = [
        {"Region": "Central", "Product": "Widget", "Sales": 1200, "Cost": 700},
    ]
    change = table_append_rows(ctx, "Sales", rows)
    assert change.type == "table.append_rows"
    assert change.after["rows_added"] == 1
    ctx.close()


def test_table_append_rows_strict_schema(simple_workbook: Path):
    ctx = WorkbookContext(simple_workbook)
    rows = [{"Region": "Central", "Product": "Widget"}]  # missing Sales, Cost
    with pytest.raises(ValueError, match="Missing columns"):
        table_append_rows(ctx, "Sales", rows, schema_mode="strict")
    ctx.close()


def test_table_append_rows_extra_columns(simple_workbook: Path):
    ctx = WorkbookContext(simple_workbook)
    rows = [
        {"Region": "Central", "Product": "Widget", "Sales": 100, "Cost": 50, "Extra": "bad"},
    ]
    with pytest.raises(ValueError, match="Extra columns"):
        table_append_rows(ctx, "Sales", rows, schema_mode="strict")
    ctx.close()


def test_cell_set(simple_workbook: Path):
    ctx = WorkbookContext(simple_workbook)
    change = cell_set(ctx, "Revenue", "A2", "Updated")
    assert change.type == "cell.set"
    assert change.before == "North"
    assert change.after == "Updated"
    ctx.close()


def test_cell_set_formula_overwrite_blocked(simple_workbook: Path):
    ctx = WorkbookContext(simple_workbook)
    # Summary!B1 has a formula
    with pytest.raises(ValueError, match="formula"):
        cell_set(ctx, "Summary", "B1", 999)
    ctx.close()


def test_cell_set_formula_overwrite_forced(simple_workbook: Path):
    ctx = WorkbookContext(simple_workbook)
    change = cell_set(ctx, "Summary", "B1", 999, force_overwrite_formulas=True)
    assert change.after == 999
    ctx.close()


def test_format_number(simple_workbook: Path):
    ctx = WorkbookContext(simple_workbook)
    change = format_number(ctx, "Revenue", "C2:C5", style="number", decimals=2)
    assert change.type == "format.number"
    assert change.impact["cells"] == 4

    # Verify format was applied
    ws = ctx.wb["Revenue"]
    assert ws.cell(row=2, column=3).number_format == "#,##0.00"
    ctx.close()


def test_format_percent(simple_workbook: Path):
    ctx = WorkbookContext(simple_workbook)
    change = format_number(ctx, "Revenue", "C2:C5", style="percent", decimals=1)
    ws = ctx.wb["Revenue"]
    assert ws.cell(row=2, column=3).number_format == "0.0%"
    ctx.close()
