"""Validation logic for workbooks and patch plans."""

from __future__ import annotations

from typing import Any

from xl.contracts.common import ErrorDetail, WarningDetail
from xl.contracts.plans import PatchPlan, Precondition
from xl.contracts.responses import ValidationResult
from xl.engine.context import WorkbookContext


def _check_precondition(ctx: WorkbookContext, pre: Precondition) -> dict[str, Any]:
    """Check a single precondition. Returns a check result dict."""
    if pre.type == "sheet_exists":
        ok = pre.sheet in ctx.wb.sheetnames if pre.sheet else False
        return {
            "type": pre.type,
            "target": pre.sheet,
            "passed": ok,
            "message": f"Sheet '{pre.sheet}' exists" if ok else f"Sheet '{pre.sheet}' not found",
        }
    elif pre.type == "table_exists":
        found = ctx.find_table(pre.table) is not None if pre.table else False
        return {
            "type": pre.type,
            "target": pre.table,
            "passed": found,
            "message": f"Table '{pre.table}' exists" if found else f"Table '{pre.table}' not found",
        }
    elif pre.type == "column_exists":
        if pre.table:
            result = ctx.find_table(pre.table)
            if result:
                _, tbl = result
                col_names = [tc.name for tc in tbl.tableColumns]
                found = pre.column in col_names if pre.column else False
                return {
                    "type": pre.type,
                    "target": f"{pre.table}[{pre.column}]",
                    "passed": found,
                    "message": f"Column '{pre.column}' exists in table '{pre.table}'" if found
                    else f"Column '{pre.column}' not found in table '{pre.table}'",
                }
        return {
            "type": pre.type,
            "target": pre.column,
            "passed": False,
            "message": f"Cannot check column: table '{pre.table}' not found",
        }
    return {
        "type": pre.type,
        "passed": False,
        "message": f"Unknown precondition type: {pre.type}",
    }


def validate_plan(ctx: WorkbookContext, plan: PatchPlan) -> ValidationResult:
    """Validate a patch plan against the current workbook state."""
    checks: list[dict[str, Any]] = []
    planned_columns_by_table: dict[str, set[str]] = {}

    # Check fingerprint
    if plan.target.fingerprint and plan.options.fail_on_external_change:
        fp_ok = plan.target.fingerprint == ctx.fp
        checks.append({
            "type": "fingerprint_match",
            "passed": fp_ok,
            "expected": plan.target.fingerprint,
            "actual": ctx.fp,
            "message": "Fingerprint matches" if fp_ok else "Fingerprint mismatch — workbook changed since plan was created",
        })

    # Check preconditions
    for pre in plan.preconditions:
        checks.append(_check_precondition(ctx, pre))

    # Validate operations
    for op in plan.operations:
        if op.type == "table.add_column":
            if op.table:
                result = ctx.find_table(op.table)
                if result is None:
                    checks.append({
                        "type": "operation_valid",
                        "op_id": op.op_id,
                        "passed": False,
                        "message": f"Table '{op.table}' not found for operation {op.op_id}",
                    })
                else:
                    ws, tbl = result
                    col_names = {tc.name.casefold() for tc in tbl.tableColumns if tc.name}
                    # Fallback: check header row when tableColumns is not populated
                    if not col_names and tbl.ref:
                        from xl.adapters.openpyxl_engine import _parse_ref
                        hdr_min_row, hdr_min_col, _, hdr_max_col = _parse_ref(tbl.ref)
                        for c in range(hdr_min_col, hdr_max_col + 1):
                            v = ws.cell(row=hdr_min_row, column=c).value
                            if v:
                                col_names.add(str(v).casefold())
                    planned = planned_columns_by_table.setdefault(op.table, set())
                    new_name = (op.name or "").casefold()
                    if new_name in col_names or new_name in planned:
                        checks.append({
                            "type": "operation_valid",
                            "op_id": op.op_id,
                            "passed": False,
                            "message": f"Column '{op.name}' already exists in table '{op.table}'",
                        })
                    else:
                        planned.add(new_name)
                        checks.append({
                            "type": "operation_valid",
                            "op_id": op.op_id,
                            "passed": True,
                            "message": f"Operation {op.op_id} is valid",
                        })
        elif op.type == "table.append_rows":
            if op.table:
                result = ctx.find_table(op.table)
                if result is None:
                    checks.append({
                        "type": "operation_valid",
                        "op_id": op.op_id,
                        "passed": False,
                        "message": f"Table '{op.table}' not found for operation {op.op_id}",
                    })
                else:
                    checks.append({
                        "type": "operation_valid",
                        "op_id": op.op_id,
                        "passed": True,
                        "message": f"Operation {op.op_id} is valid",
                    })
        elif op.type == "table.create":
            if op.sheet and op.sheet not in ctx.wb.sheetnames:
                checks.append({
                    "type": "operation_valid",
                    "op_id": op.op_id,
                    "passed": False,
                    "message": f"Sheet '{op.sheet}' not found for operation {op.op_id}",
                })
            elif op.table and ctx.find_table(op.table) is not None:
                checks.append({
                    "type": "operation_valid",
                    "op_id": op.op_id,
                    "passed": False,
                    "message": f"Table '{op.table}' already exists (operation {op.op_id})",
                })
            elif op.ref and op.sheet:
                from xl.adapters.openpyxl_engine import _parse_ref
                ws = ctx.wb[op.sheet]
                min_row, min_col, max_row, max_col = _parse_ref(op.ref)
                overlap_found = False
                for tbl in ws._tables.values():
                    t_min_row, t_min_col, t_max_row, t_max_col = _parse_ref(tbl.ref)
                    if not (max_row < t_min_row or min_row > t_max_row or
                            max_col < t_min_col or min_col > t_max_col):
                        overlap_found = True
                        checks.append({
                            "type": "operation_valid",
                            "op_id": op.op_id,
                            "passed": False,
                            "message": f"Range {op.ref} overlaps table '{tbl.displayName}' at {tbl.ref}",
                        })
                        break
                if not overlap_found:
                    checks.append({
                        "type": "operation_valid",
                        "op_id": op.op_id,
                        "passed": True,
                        "message": f"Operation {op.op_id} is valid",
                    })
            else:
                checks.append({
                    "type": "operation_valid",
                    "op_id": op.op_id,
                    "passed": True,
                    "message": f"Operation {op.op_id} is valid",
                })
        else:
            checks.append({
                "type": "operation_valid",
                "op_id": op.op_id,
                "passed": True,
                "message": f"Operation {op.op_id} accepted",
            })

    valid = all(c.get("passed", True) for c in checks)
    return ValidationResult(valid=valid, checks=checks)


def validate_workbook(ctx: WorkbookContext) -> ValidationResult:
    """Run hygiene checks on a workbook."""
    checks: list[dict[str, Any]] = []
    meta = ctx.get_workbook_meta()

    if meta.has_macros:
        checks.append({
            "type": "workbook_hygiene",
            "category": "macros",
            "passed": True,
            "severity": "warning",
            "message": "Workbook contains VBA macros. xl will not execute them.",
        })

    if meta.has_external_links:
        checks.append({
            "type": "workbook_hygiene",
            "category": "external_links",
            "passed": True,
            "severity": "warning",
            "message": "Workbook contains external links.",
        })

    # Check for hidden sheets
    hidden = [s for s in meta.sheets if s.visible != "visible"]
    if hidden:
        checks.append({
            "type": "workbook_hygiene",
            "category": "hidden_sheets",
            "passed": True,
            "severity": "info",
            "message": f"Workbook has {len(hidden)} hidden sheet(s): {[s.name for s in hidden]}",
        })

    if not checks:
        checks.append({
            "type": "workbook_hygiene",
            "passed": True,
            "message": "No issues detected.",
        })

    valid = all(c.get("passed", True) for c in checks)
    return ValidationResult(valid=valid, checks=checks)
