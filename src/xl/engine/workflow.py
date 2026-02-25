"""Workflow engine for ``xl run`` — executes YAML workflow specs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from xl.contracts.workflow import WorkflowSpec
from xl.io.fileops import read_text_safe


# All supported step commands for ``xl run`` workflows.
WORKFLOW_COMMANDS: frozenset[str] = frozenset({
    # Inspection / reading
    "wb.inspect", "sheet.ls", "table.ls",
    "cell.get", "range.stat", "query",
    "formula.find", "formula.lint",
    # Mutation
    "table.add_column", "table.append_rows",
    "cell.set", "formula.set",
    "format.number", "format.width", "format.freeze",
    "range.clear",
    # Plan / validation / verification
    "validate.plan", "validate.workbook", "validate.refs",
    "verify.assert",
    # Apply / diff
    "apply", "diff.compare",
})


def load_workflow(path: str | Path) -> WorkflowSpec:
    """Load a workflow spec from a YAML file."""
    text = read_text_safe(path)
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError("Workflow YAML must be a mapping/object.")

    allowed_keys = {"schema_version", "name", "target", "defaults", "steps"}
    unknown_keys = sorted(set(data) - allowed_keys)
    if unknown_keys:
        raise ValueError(f"Unknown workflow keys: {', '.join(unknown_keys)}")

    steps = data.get("steps")
    if not isinstance(steps, list):
        raise ValueError("Workflow must define 'steps' as an array.")
    if not steps:
        raise ValueError("Workflow must contain at least one step.")

    return WorkflowSpec(**data)


_MUTATING_STEPS = frozenset({
    "table.add_column", "table.append_rows", "cell.set", "formula.set",
    "format.number", "format.width", "format.freeze", "range.clear",
    "apply",
})


def _split_ref(ref: str) -> tuple[str, str]:
    """Split 'Sheet!CellOrRange' into (sheet_name, cell_ref)."""
    if "!" in ref:
        return ref.split("!", 1)
    return ("", ref)


def _run_query(ctx: Any, sql: str) -> dict[str, Any]:
    """Execute a DuckDB query against workbook tables."""
    import duckdb

    from xl.adapters.openpyxl_engine import _parse_ref

    conn = duckdb.connect()
    try:
        tables = ctx.list_tables()
        for tbl in tables:
            ws = ctx.wb[tbl.sheet]
            min_row, min_col, max_row, max_col = _parse_ref(tbl.ref)
            col_names = [tc.name for tc in tbl.columns]
            data_rows = []
            for row_idx in range(min_row + 1, max_row + 1):
                row_data = {}
                for ci, col_name in enumerate(col_names):
                    cell = ws.cell(row=row_idx, column=min_col + ci)
                    row_data[col_name] = cell.value
                data_rows.append(row_data)
            if data_rows:
                col_defs = []
                for col_name in col_names:
                    sample = data_rows[0].get(col_name)
                    if isinstance(sample, int):
                        col_defs.append(f'"{col_name}" BIGINT')
                    elif isinstance(sample, float):
                        col_defs.append(f'"{col_name}" DOUBLE')
                    else:
                        col_defs.append(f'"{col_name}" VARCHAR')
                conn.execute(f'CREATE TABLE "{tbl.name}" ({", ".join(col_defs)})')
                placeholders = ", ".join(["?"] * len(col_names))
                insert_sql = f'INSERT INTO "{tbl.name}" VALUES ({placeholders})'
                rows_to_insert = [tuple(r.get(c) for c in col_names) for r in data_rows]
                conn.executemany(insert_sql, rows_to_insert)
        cursor = conn.execute(sql)
        columns = [desc[0] for desc in cursor.description]
        raw_rows = cursor.fetchall()
        rows = [dict(zip(columns, row)) for row in raw_rows]
        return {"columns": columns, "rows": rows, "row_count": len(rows)}
    finally:
        conn.close()


def execute_workflow(
    workflow: WorkflowSpec,
    workbook_path: str | Path,
) -> dict[str, Any]:
    """Execute a workflow against a workbook. Returns combined results."""
    from xl.adapters.openpyxl_engine import (
        cell_get,
        cell_set,
        format_freeze,
        format_number,
        format_width,
        formula_find,
        formula_lint,
        formula_set,
        range_clear,
        range_stat,
        table_add_column,
        table_append_rows,
    )
    from xl.engine.context import WorkbookContext
    from xl.validation.validators import validate_plan, validate_workbook

    results: list[dict[str, Any]] = []

    # Pre-scan: open in data_only mode when no step can mutate, so cached
    # formula values are preserved and the workbook stays identical on disk.
    has_mutating_steps = any(s.run in _MUTATING_STEPS for s in workflow.steps)
    ctx = WorkbookContext(workbook_path, data_only=not has_mutating_steps)
    mutated = False

    for step in workflow.steps:
        step_result: dict[str, Any] = {"step_id": step.id, "run": step.run}
        try:
            # -- Inspection / reading --
            if step.run == "wb.inspect":
                meta = ctx.get_workbook_meta()
                step_result["result"] = meta.model_dump()
                step_result["ok"] = True

            elif step.run == "sheet.ls":
                sheets = ctx.list_sheets()
                step_result["result"] = [s.model_dump() for s in sheets]
                step_result["ok"] = True

            elif step.run == "table.ls":
                tables = ctx.list_tables(step.args.get("sheet"))
                step_result["result"] = [t.model_dump() for t in tables]
                step_result["ok"] = True

            elif step.run == "cell.get":
                ref = step.args.get("ref", "")
                sheet_name, cell_ref = _split_ref(ref)
                result_data = cell_get(ctx, sheet_name, cell_ref)
                step_result["result"] = result_data
                step_result["ok"] = True

            elif step.run == "range.stat":
                ref = step.args.get("ref", "")
                sheet_name, range_ref = _split_ref(ref)
                result_data = range_stat(ctx, sheet_name, range_ref)
                step_result["result"] = result_data
                step_result["ok"] = True

            elif step.run == "query":
                sql = step.args.get("sql", "")
                result_data = _run_query(ctx, sql)
                step_result["result"] = result_data
                step_result["ok"] = True

            elif step.run == "formula.find":
                pattern = step.args.get("pattern", "")
                sheet = step.args.get("sheet")
                matches = formula_find(ctx, pattern, sheet_name=sheet)
                step_result["result"] = matches
                step_result["ok"] = True

            elif step.run == "formula.lint":
                sheet = step.args.get("sheet")
                findings = formula_lint(ctx, sheet_name=sheet)
                step_result["result"] = findings
                step_result["ok"] = True

            # -- Mutation --
            elif step.run == "table.add_column":
                change = table_add_column(
                    ctx,
                    step.args["table"],
                    step.args["name"],
                    formula=step.args.get("formula"),
                    default_value=step.args.get("default_value"),
                )
                mutated = True
                step_result["result"] = change.model_dump()
                step_result["ok"] = True

            elif step.run == "table.append_rows":
                rows = step.args.get("rows", [])
                change = table_append_rows(
                    ctx,
                    step.args["table"],
                    rows,
                    schema_mode=step.args.get("schema_mode", "strict"),
                )
                mutated = True
                step_result["result"] = change.model_dump()
                step_result["ok"] = True

            elif step.run == "cell.set":
                ref = step.args["ref"]
                sheet_name, cell_ref = _split_ref(ref)
                change = cell_set(ctx, sheet_name, cell_ref, step.args["value"])
                mutated = True
                step_result["result"] = change.model_dump()
                step_result["ok"] = True

            elif step.run == "formula.set":
                ref = step.args["ref"]
                sheet_name, cell_ref = _split_ref(ref)
                change = formula_set(
                    ctx, sheet_name, cell_ref, step.args["formula"],
                    force_overwrite_values=step.args.get("force_overwrite_values", False),
                    force_overwrite_formulas=step.args.get("force_overwrite_formulas", False),
                )
                mutated = True
                step_result["result"] = change.model_dump()
                step_result["ok"] = True

            elif step.run == "format.number":
                ref = step.args.get("ref", "")
                sheet_name, range_ref = _split_ref(ref)
                change = format_number(
                    ctx, sheet_name, range_ref,
                    style=step.args.get("style", "number"),
                    decimals=step.args.get("decimals", 2),
                )
                mutated = True
                step_result["result"] = change.model_dump()
                step_result["ok"] = True

            elif step.run == "format.width":
                sheet_name = step.args.get("sheet", "")
                columns = step.args.get("columns", [])
                width = step.args.get("width", 10)
                change = format_width(ctx, sheet_name, columns, width)
                mutated = True
                step_result["result"] = change.model_dump()
                step_result["ok"] = True

            elif step.run == "format.freeze":
                sheet_name = step.args.get("sheet", "")
                ref = step.args.get("ref")
                change = format_freeze(ctx, sheet_name, ref)
                mutated = True
                step_result["result"] = change.model_dump()
                step_result["ok"] = True

            elif step.run == "range.clear":
                ref = step.args.get("ref", "")
                sheet_name, range_ref = _split_ref(ref)
                change = range_clear(
                    ctx, sheet_name, range_ref,
                    contents=step.args.get("contents", True),
                    formats=step.args.get("formats", False),
                )
                mutated = True
                step_result["result"] = change.model_dump()
                step_result["ok"] = True

            # -- Plan / validation / verification --
            elif step.run == "validate.plan":
                from xl.contracts.plans import PatchPlan
                plan_data = step.args.get("plan")
                if isinstance(plan_data, str):
                    plan_data = json.loads(read_text_safe(plan_data))
                plan = PatchPlan(**plan_data)
                vr = validate_plan(ctx, plan)
                step_result["result"] = vr.model_dump()
                step_result["ok"] = vr.valid

            elif step.run == "validate.workbook":
                vr = validate_workbook(ctx)
                step_result["result"] = vr.model_dump()
                step_result["ok"] = vr.valid

            elif step.run == "validate.refs":
                from xl.adapters.openpyxl_engine import _parse_ref
                ref = step.args.get("ref", "")
                checks: list[dict[str, Any]] = []
                if "!" in ref:
                    sheet_name, range_ref = ref.split("!", 1)
                    if sheet_name in ctx.wb.sheetnames:
                        checks.append({"type": "sheet_exists", "target": sheet_name, "passed": True})
                        try:
                            _parse_ref(range_ref)
                            checks.append({"type": "range_valid", "target": ref, "passed": True})
                        except ValueError as e:
                            checks.append({"type": "range_valid", "target": ref, "passed": False, "message": str(e)})
                    else:
                        checks.append({"type": "sheet_exists", "target": sheet_name, "passed": False})
                else:
                    checks.append({"type": "ref_format", "target": ref, "passed": False, "message": "Ref must include sheet name"})
                valid = all(c.get("passed") for c in checks)
                step_result["result"] = {"valid": valid, "checks": checks}
                step_result["ok"] = valid

            elif step.run == "verify.assert":
                from xl.engine.verify import run_assertions
                assertions = step.args.get("assertions", [])
                assertion_results = run_assertions(ctx, assertions)
                step_result["result"] = assertion_results
                step_result["ok"] = all(r.get("passed", False) for r in assertion_results)

            # -- Apply / diff --
            elif step.run == "apply":
                from xl.contracts.plans import PatchPlan
                plan_data = step.args.get("plan")
                if isinstance(plan_data, str):
                    plan_data = json.loads(read_text_safe(plan_data))
                plan = PatchPlan(**plan_data)
                vr = validate_plan(ctx, plan)
                if not vr.valid:
                    step_result["result"] = vr.model_dump()
                    step_result["ok"] = False
                else:
                    changes = []
                    for op in plan.operations:
                        if op.type == "table.add_column":
                            change = table_add_column(ctx, op.table, op.name, formula=op.formula, default_value=op.value)
                            changes.append(change.model_dump())
                        elif op.type == "table.append_rows":
                            change = table_append_rows(ctx, op.table, op.rows or [])
                            changes.append(change.model_dump())
                    mutated = True
                    step_result["result"] = {"applied": True, "operations": len(changes), "changes": changes}
                    step_result["ok"] = True

            elif step.run == "diff.compare":
                from xl.diff.differ import diff_workbooks
                file_a = step.args.get("file_a", "")
                file_b = step.args.get("file_b", "")
                sheet = step.args.get("sheet")
                result_data = diff_workbooks(file_a, file_b, sheet_filter=sheet)
                step_result["result"] = result_data
                step_result["ok"] = True

            else:
                step_result["ok"] = False
                step_result["error"] = f"Unknown step command: {step.run}"

        except Exception as e:
            step_result["ok"] = False
            step_result["error"] = str(e)

        results.append(step_result)

    # Save if not dry_run
    if not workflow.defaults.dry_run and mutated:
        ctx.save(workbook_path)

    ctx.close()

    all_ok = all(r.get("ok", False) for r in results)
    return {
        "workflow": workflow.name,
        "steps_total": len(workflow.steps),
        "steps_passed": sum(1 for r in results if r.get("ok")),
        "ok": all_ok,
        "steps": results,
    }
