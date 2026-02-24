"""openpyxl-based workbook operations for table mutations, cell/range ops."""

from __future__ import annotations

import re
from typing import Any

from openpyxl.utils import column_index_from_string, get_column_letter
from openpyxl.worksheet.table import Table, TableColumn
from openpyxl.worksheet.worksheet import Worksheet

from xl.contracts.common import ChangeRecord, WarningDetail
from xl.engine.context import WorkbookContext


def _parse_ref(ref: str) -> tuple[int, int, int, int]:
    """Parse A1:B2 style ref into (min_row, min_col, max_row, max_col)."""
    parts = ref.replace("$", "").split(":")
    m1 = re.match(r"([A-Z]+)(\d+)", parts[0])
    if not m1:
        raise ValueError(f"Invalid ref: {ref}")
    min_col = column_index_from_string(m1.group(1))
    min_row = int(m1.group(2))
    if len(parts) == 2:
        m2 = re.match(r"([A-Z]+)(\d+)", parts[1])
        if not m2:
            raise ValueError(f"Invalid ref: {ref}")
        max_col = column_index_from_string(m2.group(1))
        max_row = int(m2.group(2))
    else:
        max_col = min_col
        max_row = min_row
    return min_row, min_col, max_row, max_col


def table_add_column(
    ctx: WorkbookContext,
    table_name: str,
    column_name: str,
    *,
    formula: str | None = None,
    default_value: Any | None = None,
    position: str = "append",
) -> ChangeRecord:
    """Add a column to an Excel Table."""
    result = ctx.find_table(table_name)
    if result is None:
        raise ValueError(f"Table not found: {table_name}")
    ws, tbl = result

    ref = tbl.ref
    min_row, min_col, max_row, max_col = _parse_ref(ref)
    new_col_idx = max_col + 1
    new_col_letter = get_column_letter(new_col_idx)

    # Write header
    ws.cell(row=min_row, column=new_col_idx, value=column_name)

    # Fill data rows
    for row in range(min_row + 1, max_row + 1):
        if formula:
            ws.cell(row=row, column=new_col_idx, value=formula)
        elif default_value is not None:
            ws.cell(row=row, column=new_col_idx, value=default_value)

    # Update table ref
    new_ref = f"{get_column_letter(min_col)}{min_row}:{new_col_letter}{max_row}"
    tbl.ref = new_ref

    # Add table column
    new_tc = TableColumn(id=len(tbl.tableColumns) + 1, name=column_name)
    tbl.tableColumns.append(new_tc)

    return ChangeRecord(
        type="table.add_column",
        target=f"{table_name}[{column_name}]",
        after={"column": column_name, "formula": formula, "default_value": default_value},
        impact={"rows": max_row - min_row, "cells": max_row - min_row},
    )


def table_append_rows(
    ctx: WorkbookContext,
    table_name: str,
    rows: list[dict[str, Any]],
    *,
    schema_mode: str = "strict",
) -> ChangeRecord:
    """Append rows to an Excel Table."""
    result = ctx.find_table(table_name)
    if result is None:
        raise ValueError(f"Table not found: {table_name}")
    ws, tbl = result

    ref = tbl.ref
    min_row, min_col, max_row, max_col = _parse_ref(ref)

    # Get column names from table
    col_names = [tc.name for tc in tbl.tableColumns]

    warnings: list[WarningDetail] = []

    for row_data in rows:
        if schema_mode == "strict":
            extra = set(row_data.keys()) - set(col_names)
            missing = set(col_names) - set(row_data.keys())
            if extra:
                raise ValueError(f"Extra columns not in table schema: {extra}")
            if missing:
                raise ValueError(f"Missing columns in row data: {missing}")

        max_row += 1
        for col_idx, col_name in enumerate(col_names, start=min_col):
            val = row_data.get(col_name)
            ws.cell(row=max_row, column=col_idx, value=val)

    # Update table ref
    new_ref = f"{get_column_letter(min_col)}{min_row}:{get_column_letter(max_col)}{max_row}"
    tbl.ref = new_ref

    return ChangeRecord(
        type="table.append_rows",
        target=table_name,
        after={"rows_added": len(rows)},
        impact={"rows": len(rows), "cells": len(rows) * len(col_names)},
        warnings=warnings,
    )


def cell_set(
    ctx: WorkbookContext,
    sheet_name: str,
    ref: str,
    value: Any,
    *,
    cell_type: str | None = None,
    force_overwrite_formulas: bool = False,
) -> ChangeRecord:
    """Set a single cell value."""
    ws = ctx.get_sheet(sheet_name)
    m = re.match(r"([A-Z]+)(\d+)", ref.replace("$", ""))
    if not m:
        raise ValueError(f"Invalid cell ref: {ref}")
    col = column_index_from_string(m.group(1))
    row = int(m.group(2))

    cell = ws.cell(row=row, column=col)
    old_val = cell.value

    # Check formula overwrite
    if isinstance(old_val, str) and old_val.startswith("=") and not force_overwrite_formulas:
        if not (isinstance(value, str) and value.startswith("=")):
            raise ValueError(
                f"Cell {ref} contains formula '{old_val}'. "
                "Use --force-overwrite-formulas to overwrite."
            )

    # Type coercion
    if cell_type == "number" and not isinstance(value, (int, float)):
        value = float(value)
    elif cell_type == "bool":
        value = bool(value)

    cell.value = value

    return ChangeRecord(
        type="cell.set",
        target=f"{sheet_name}!{ref}",
        before=old_val,
        after=value,
        impact={"cells": 1},
    )


def format_number(
    ctx: WorkbookContext,
    sheet_name: str,
    ref: str,
    *,
    style: str = "number",
    decimals: int = 2,
) -> ChangeRecord:
    """Apply number format to a range."""
    ws = ctx.get_sheet(sheet_name)
    min_row, min_col, max_row, max_col = _parse_ref(ref)

    fmt_map = {
        "number": f"#,##0.{'0' * decimals}",
        "percent": f"0.{'0' * decimals}%",
        "currency": f"$#,##0.{'0' * decimals}",
        "date": "YYYY-MM-DD",
        "text": "@",
    }
    fmt = fmt_map.get(style, style)

    cells_touched = 0
    for row in range(min_row, max_row + 1):
        for col in range(min_col, max_col + 1):
            ws.cell(row=row, column=col).number_format = fmt
            cells_touched += 1

    return ChangeRecord(
        type="format.number",
        target=f"{sheet_name}!{ref}",
        after={"format": fmt, "style": style, "decimals": decimals},
        impact={"cells": cells_touched},
    )


def resolve_table_column_ref(ctx: WorkbookContext, ref: str) -> tuple[str, str] | None:
    """Resolve 'TableName[ColumnName]' to (sheet_name, A1_range)."""
    m = re.match(r"(\w+)\[(\w+)\]", ref)
    if not m:
        return None
    table_name, col_name = m.group(1), m.group(2)
    result = ctx.find_table(table_name)
    if result is None:
        return None
    ws, tbl = result
    sheet_name = ws.title

    tbl_ref = tbl.ref
    min_row, min_col, max_row, max_col = _parse_ref(tbl_ref)
    for i, tc in enumerate(tbl.tableColumns):
        if tc.name == col_name:
            col_idx = min_col + i
            col_letter = get_column_letter(col_idx)
            return sheet_name, f"{col_letter}{min_row}:{col_letter}{max_row}"
    return None
