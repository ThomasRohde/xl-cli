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
                    _, tbl = result
                    col_names = [tc.name for tc in tbl.tableColumns]
                    if op.name in col_names:
                        checks.append({
                            "type": "operation_valid",
                            "op_id": op.op_id,
                            "passed": False,
                            "message": f"Column '{op.name}' already exists in table '{op.table}'",
                        })
                    else:
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
