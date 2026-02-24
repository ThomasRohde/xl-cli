"""Post-apply assertion engine for ``xl verify``."""

from __future__ import annotations

from typing import Any

from xl.engine.context import WorkbookContext


def run_assertions(
    ctx: WorkbookContext,
    assertions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Run a list of assertions against the workbook. Returns results."""
    results: list[dict[str, Any]] = []
    for assertion in assertions:
        a_type = assertion.get("type", "")
        try:
            result = _check_assertion(ctx, assertion)
        except Exception as e:
            result = {
                "type": a_type,
                "passed": False,
                "message": f"Assertion error: {e}",
            }
        results.append(result)
    return results


def _check_assertion(ctx: WorkbookContext, assertion: dict[str, Any]) -> dict[str, Any]:
    a_type = assertion["type"]

    if a_type == "table.column_exists":
        table_name = assertion["table"]
        column = assertion["column"]
        result = ctx.find_table(table_name)
        if result is None:
            return {"type": a_type, "passed": False, "message": f"Table '{table_name}' not found"}
        _, tbl = result
        col_names = [tc.name for tc in tbl.tableColumns]
        found = column in col_names
        return {
            "type": a_type,
            "passed": found,
            "expected": column,
            "actual": col_names,
            "message": f"Column '{column}' {'exists' if found else 'not found'} in table '{table_name}'",
        }

    elif a_type == "table.row_count":
        table_name = assertion["table"]
        result = ctx.find_table(table_name)
        if result is None:
            return {"type": a_type, "passed": False, "message": f"Table '{table_name}' not found"}
        from xl.adapters.openpyxl_engine import _parse_ref
        _, tbl = result
        min_row, _, max_row, _ = _parse_ref(tbl.ref)
        actual_count = max_row - min_row  # exclude header
        expected = assertion.get("expected")
        min_val = assertion.get("min")
        max_val = assertion.get("max")

        passed = True
        msg_parts = []
        if expected is not None:
            passed = actual_count == expected
            msg_parts.append(f"expected={expected}")
        if min_val is not None and actual_count < min_val:
            passed = False
            msg_parts.append(f"min={min_val}")
        if max_val is not None and actual_count > max_val:
            passed = False
            msg_parts.append(f"max={max_val}")

        return {
            "type": a_type,
            "passed": passed,
            "actual": actual_count,
            "message": f"Table '{table_name}' row count={actual_count} ({', '.join(msg_parts) if msg_parts else 'ok'})",
        }

    elif a_type == "cell.value_equals":
        ref = assertion["ref"]
        expected = assertion["expected"]
        sheet_name, cell_ref = ref.split("!", 1) if "!" in ref else ("", ref)
        from xl.adapters.openpyxl_engine import cell_get
        cell_data = cell_get(ctx, sheet_name, cell_ref)
        actual = cell_data["value"]
        # Flexible comparison: compare as strings if types differ
        passed = actual == expected or str(actual) == str(expected)
        return {
            "type": a_type,
            "passed": passed,
            "expected": expected,
            "actual": actual,
            "message": f"Cell {ref}: {'matches' if passed else f'expected {expected!r}, got {actual!r}'}",
        }

    elif a_type == "cell.not_empty":
        ref = assertion["ref"]
        sheet_name, cell_ref = ref.split("!", 1) if "!" in ref else ("", ref)
        from xl.adapters.openpyxl_engine import cell_get
        cell_data = cell_get(ctx, sheet_name, cell_ref)
        passed = cell_data["value"] is not None
        return {
            "type": a_type,
            "passed": passed,
            "message": f"Cell {ref}: {'not empty' if passed else 'is empty'}",
        }

    elif a_type == "cell.value_type":
        ref = assertion["ref"]
        expected_type = assertion["expected_type"]
        sheet_name, cell_ref = ref.split("!", 1) if "!" in ref else ("", ref)
        from xl.adapters.openpyxl_engine import cell_get
        cell_data = cell_get(ctx, sheet_name, cell_ref)
        actual_type = cell_data["type"]
        passed = actual_type == expected_type
        return {
            "type": a_type,
            "passed": passed,
            "expected": expected_type,
            "actual": actual_type,
            "message": f"Cell {ref}: type {'matches' if passed else f'expected {expected_type}, got {actual_type}'}",
        }

    return {"type": a_type, "passed": False, "message": f"Unknown assertion type: {a_type}"}
