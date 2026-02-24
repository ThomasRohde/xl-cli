"""Tests for WorkbookContext."""

from pathlib import Path

import pytest

from xl.engine.context import WorkbookContext


def test_workbook_context_load(simple_workbook: Path):
    ctx = WorkbookContext(simple_workbook)
    assert ctx.fp.startswith("sha256:")
    assert ctx.path == simple_workbook.resolve()
    ctx.close()


def test_workbook_context_not_found(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        WorkbookContext(tmp_path / "nonexistent.xlsx")


def test_get_workbook_meta(simple_workbook: Path):
    ctx = WorkbookContext(simple_workbook)
    meta = ctx.get_workbook_meta()
    assert meta.path == str(simple_workbook.resolve())
    assert meta.fingerprint.startswith("sha256:")
    assert len(meta.sheets) == 2
    assert meta.sheets[0].name == "Revenue"
    assert meta.sheets[1].name == "Summary"
    assert meta.has_macros is False
    ctx.close()


def test_list_sheets(simple_workbook: Path):
    ctx = WorkbookContext(simple_workbook)
    sheets = ctx.list_sheets()
    assert len(sheets) == 2
    names = [s.name for s in sheets]
    assert "Revenue" in names
    assert "Summary" in names
    ctx.close()


def test_list_tables(simple_workbook: Path):
    ctx = WorkbookContext(simple_workbook)
    tables = ctx.list_tables()
    assert len(tables) == 1
    assert tables[0].name == "Sales"
    assert tables[0].sheet == "Revenue"
    assert len(tables[0].columns) == 4
    col_names = [c.name for c in tables[0].columns]
    assert "Region" in col_names
    assert "Sales" in col_names
    ctx.close()


def test_list_tables_filter_by_sheet(simple_workbook: Path):
    ctx = WorkbookContext(simple_workbook)
    tables = ctx.list_tables(sheet="Summary")
    assert len(tables) == 0
    tables = ctx.list_tables(sheet="Revenue")
    assert len(tables) == 1
    ctx.close()


def test_find_table(simple_workbook: Path):
    ctx = WorkbookContext(simple_workbook)
    result = ctx.find_table("Sales")
    assert result is not None
    ws, tbl = result
    assert ws.title == "Revenue"

    result = ctx.find_table("NonExistent")
    assert result is None
    ctx.close()


def test_multi_table_workbook(multi_table_workbook: Path):
    ctx = WorkbookContext(multi_table_workbook)
    tables = ctx.list_tables()
    assert len(tables) == 2
    names = {t.name for t in tables}
    assert names == {"Products", "Orders"}
    ctx.close()
