"""Workflow engine for ``xl run`` — executes YAML workflow specs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from xl.contracts.workflow import WorkflowSpec
from xl.io.fileops import read_text_safe


class WorkflowValidationError(ValueError):
    """Raised when workflow validation fails with structured details."""

    def __init__(self, message: str, details: list[dict[str, Any]]) -> None:
        super().__init__(message)
        self.details = details


# Schema defining required/optional args per workflow step command.
STEP_ARG_SCHEMA: dict[str, dict[str, list[str]]] = {
    "wb.inspect": {"required": [], "optional": []},
    "sheet.ls": {"required": [], "optional": []},
    "table.ls": {"required": [], "optional": ["sheet"]},
    "cell.get": {"required": ["ref"], "optional": []},
    "range.stat": {"required": ["ref"], "optional": []},
    "query": {"required": ["sql"], "optional": []},
    "formula.find": {"required": ["pattern"], "optional": ["sheet"]},
    "formula.lint": {"required": [], "optional": ["sheet"]},
    "table.create": {"required": ["sheet", "table", "ref"], "optional": ["columns", "style"]},
    "table.add_column": {"required": ["table", "name"], "optional": ["formula", "default_value"]},
    "table.append_rows": {"required": ["table", "rows"], "optional": ["schema_mode"]},
    "cell.set": {"required": ["ref", "value"], "optional": ["force_overwrite_formulas", "type"]},
    "formula.set": {"required": ["ref", "formula"], "optional": ["force_overwrite_values", "force_overwrite_formulas", "fill_mode"]},
    "format.number": {"required": ["ref"], "optional": ["style", "decimals"]},
    "format.width": {"required": ["sheet", "columns", "width"], "optional": []},
    "format.freeze": {"required": ["sheet"], "optional": ["ref"]},
    "range.clear": {"required": ["ref"], "optional": ["contents", "formats"]},
    "validate.plan": {"required": ["plan"], "optional": []},
    "validate.workbook": {"required": [], "optional": []},
    "validate.refs": {"required": ["ref"], "optional": []},
    "verify.assert": {"required": ["assertions"], "optional": []},
    "apply": {"required": ["plan"], "optional": []},
    "diff.compare": {"required": ["file_a", "file_b"], "optional": ["sheet"]},
    "sheet.delete": {"required": ["name"], "optional": []},
    "sheet.rename": {"required": ["name", "new_name"], "optional": []},
    "table.delete": {"required": ["table"], "optional": []},
    "table.delete_column": {"required": ["table", "name"], "optional": []},
}


# All supported step commands for ``xl run`` workflows.
WORKFLOW_COMMANDS: frozenset[str] = frozenset({
    # Inspection / reading
    "wb.inspect", "sheet.ls", "table.ls",
    "cell.get", "range.stat", "query",
    "formula.find", "formula.lint",
    # Mutation
    "table.create", "table.add_column", "table.append_rows",
    "table.delete", "table.delete_column",
    "cell.set", "formula.set",
    "format.number", "format.width", "format.freeze",
    "range.clear",
    "sheet.delete", "sheet.rename",
    # Plan / validation / verification
    "validate.plan", "validate.workbook", "validate.refs",
    "verify.assert",
    # Apply / diff
    "apply", "diff.compare",
})


def validate_workflow(path: str | Path) -> dict[str, Any]:
    """Validate a workflow YAML file without requiring a workbook.

    Returns a ValidationResult-style dict: {valid, checks}.
    """
    from xl.contracts.responses import ValidationResult

    checks: list[dict[str, Any]] = []
    p = Path(path)

    # File readable
    if not p.exists():
        checks.append({"type": "file_readable", "passed": False, "message": f"File not found: {p}"})
        return ValidationResult(valid=False, checks=checks).model_dump()
    checks.append({"type": "file_readable", "passed": True, "message": f"File exists: {p}"})

    # YAML parse
    try:
        text = read_text_safe(p)
        data = yaml.safe_load(text)
    except Exception as e:
        checks.append({"type": "yaml_parse", "passed": False, "message": f"YAML parse error: {e}"})
        return ValidationResult(valid=False, checks=checks).model_dump()
    checks.append({"type": "yaml_parse", "passed": True, "message": "YAML parsed successfully"})

    # Root is mapping
    if not isinstance(data, dict):
        checks.append({"type": "root_mapping", "passed": False, "message": "Root must be a YAML mapping/object"})
        return ValidationResult(valid=False, checks=checks).model_dump()
    checks.append({"type": "root_mapping", "passed": True, "message": "Root is a mapping"})

    # Unknown top-level keys
    allowed_keys = {"schema_version", "name", "target", "defaults", "steps"}
    unknown_keys = sorted(set(data) - allowed_keys)
    if unknown_keys:
        checks.append({"type": "unknown_keys", "passed": False, "message": f"Unknown top-level keys: {', '.join(unknown_keys)}"})
    else:
        checks.append({"type": "unknown_keys", "passed": True, "message": "No unknown top-level keys"})

    # Steps is non-empty array
    steps = data.get("steps")
    if not isinstance(steps, list):
        checks.append({"type": "steps_array", "passed": False, "message": "'steps' must be an array"})
        valid = all(c["passed"] for c in checks)
        return ValidationResult(valid=valid, checks=checks).model_dump()
    if not steps:
        checks.append({"type": "steps_array", "passed": False, "message": "'steps' must contain at least one step"})
        valid = all(c["passed"] for c in checks)
        return ValidationResult(valid=valid, checks=checks).model_dump()
    checks.append({"type": "steps_array", "passed": True, "message": f"{len(steps)} step(s) found"})

    # Per-step validation
    seen_ids: set[str] = set()
    for i, step in enumerate(steps):
        prefix = f"steps[{i}]"
        if not isinstance(step, dict):
            checks.append({"type": "step_format", "passed": False, "message": f"{prefix}: must be a mapping"})
            continue

        # Has id
        step_id = step.get("id")
        if not step_id:
            checks.append({"type": "step_id", "passed": False, "message": f"{prefix}: missing 'id'"})
        else:
            if step_id in seen_ids:
                checks.append({"type": "step_id_unique", "passed": False, "message": f"{prefix}: duplicate id '{step_id}'"})
            else:
                checks.append({"type": "step_id", "passed": True, "message": f"{prefix}: id='{step_id}'"})
            seen_ids.add(step_id)

        # Has run
        run_cmd = step.get("run")
        if not run_cmd:
            checks.append({"type": "step_run", "passed": False, "message": f"{prefix}: missing 'run'"})
        elif run_cmd not in WORKFLOW_COMMANDS:
            checks.append({"type": "step_run_valid", "passed": False, "message": f"{prefix}: unknown command '{run_cmd}'"})
        else:
            checks.append({"type": "step_run", "passed": True, "message": f"{prefix}: run='{run_cmd}'"})

        # Args is dict (if present)
        args = step.get("args")
        if args is not None and not isinstance(args, dict):
            checks.append({"type": "step_args", "passed": False, "message": f"{prefix}: 'args' must be a mapping"})

        # Validate step args against schema
        if run_cmd and run_cmd in STEP_ARG_SCHEMA and isinstance(args, dict):
            schema = STEP_ARG_SCHEMA[run_cmd]
            required_args = set(schema["required"])
            provided_args = set(args.keys())
            all_known = required_args | set(schema["optional"])

            missing_args = required_args - provided_args
            for arg_name in sorted(missing_args):
                hint = ""
                if arg_name in step:
                    hint = f" (found '{arg_name}' at step level — move it inside 'args:')"
                checks.append({"type": "step_missing_arg", "passed": False,
                    "message": f"{prefix}: missing required arg '{arg_name}' for '{run_cmd}'{hint}"})

            unknown_args = provided_args - all_known - {"dry_run", "dry-run"}
            for arg_name in sorted(unknown_args):
                checks.append({"type": "step_unknown_arg", "passed": False,
                    "message": f"{prefix}: unknown arg '{arg_name}' for '{run_cmd}' (valid: {', '.join(sorted(all_known))})"})
        elif run_cmd and run_cmd in STEP_ARG_SCHEMA and (args is None or not isinstance(args, dict)):
            schema = STEP_ARG_SCHEMA[run_cmd]
            required_args = set(schema["required"])
            if required_args:
                # Check if required args were placed at step level
                misplaced = [a for a in sorted(required_args) if a in step]
                if misplaced:
                    hint = ", ".join(f"'{a}'" for a in misplaced)
                    checks.append({"type": "step_missing_arg", "passed": False,
                        "message": f"{prefix}: found {hint} at step level — wrap them inside 'args:' mapping"})
                else:
                    checks.append({"type": "step_missing_arg", "passed": False,
                        "message": f"{prefix}: no 'args' mapping provided but '{run_cmd}' requires: {', '.join(sorted(required_args))}"})

    valid = all(c["passed"] for c in checks)
    return ValidationResult(valid=valid, checks=checks).model_dump()


def load_workflow(path: str | Path) -> WorkflowSpec:
    """Load a workflow spec from a YAML file.

    Raises WorkflowValidationError with structured details on invalid input.
    """
    text = read_text_safe(path)
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise WorkflowValidationError(
            "Workflow YAML must be a mapping/object.",
            [{"type": "yaml_structure", "message": "Root must be a mapping/object, got " + type(data).__name__}],
        )

    allowed_keys = {"schema_version", "name", "target", "defaults", "steps"}
    unknown_keys = sorted(set(data) - allowed_keys)
    if unknown_keys:
        raise WorkflowValidationError(
            f"Unknown workflow keys: {', '.join(unknown_keys)}",
            [{"type": "unknown_key", "key": k, "message": f"Unknown top-level key: '{k}'"} for k in unknown_keys],
        )

    steps = data.get("steps")
    if not isinstance(steps, list):
        raise WorkflowValidationError(
            "Workflow must define 'steps' as an array.",
            [{"type": "missing_steps", "message": "'steps' must be a non-empty array"}],
        )
    if not steps:
        raise WorkflowValidationError(
            "Workflow must contain at least one step.",
            [{"type": "empty_steps", "message": "'steps' array is empty"}],
        )

    # Parse with Pydantic — catch validation errors for structured reporting
    import pydantic
    try:
        spec = WorkflowSpec(**data)
    except pydantic.ValidationError as e:
        details = []
        for err in e.errors():
            loc = " → ".join(str(x) for x in err.get("loc", []))
            details.append({
                "type": "pydantic_validation",
                "location": loc,
                "message": err.get("msg", str(err)),
                "input": err.get("input"),
            })
        raise WorkflowValidationError(
            f"Workflow validation failed: {len(details)} error(s)",
            details,
        ) from e

    # Validate step args against STEP_ARG_SCHEMA
    issues: list[dict[str, Any]] = []
    for i, step in enumerate(spec.steps):
        schema = STEP_ARG_SCHEMA.get(step.run)
        if schema is None:
            continue  # unknown commands already caught by Pydantic validator

        required = set(schema["required"])
        optional = set(schema["optional"])
        all_known = required | optional
        provided = set(step.args.keys())

        # Check for missing required args
        missing = required - provided
        raw_steps = data.get("steps", [])
        raw_step = raw_steps[i] if i < len(raw_steps) and isinstance(raw_steps[i], dict) else {}
        for arg_name in sorted(missing):
            hint = ""
            if arg_name in raw_step:
                hint = f" (found '{arg_name}' at step level — move it inside 'args:')"
            issues.append({
                "type": "missing_required_arg",
                "step_index": i,
                "step_id": step.id,
                "command": step.run,
                "arg": arg_name,
                "message": f"Step '{step.id}' ({step.run}): missing required arg '{arg_name}'{hint}",
            })

        # Check for unknown args
        unknown = provided - all_known - {"dry_run", "dry-run"}
        for arg_name in sorted(unknown):
            issues.append({
                "type": "unknown_arg",
                "step_index": i,
                "step_id": step.id,
                "command": step.run,
                "arg": arg_name,
                "message": f"Step '{step.id}' ({step.run}): unknown arg '{arg_name}' (valid: {', '.join(sorted(all_known))})",
            })

    if issues:
        raise WorkflowValidationError(
            f"Workflow step arg validation failed: {len(issues)} issue(s)",
            issues,
        )

    return spec


_MUTATING_STEPS = frozenset({
    "table.create", "table.add_column", "table.append_rows",
    "table.delete", "table.delete_column",
    "cell.set", "formula.set",
    "format.number", "format.width", "format.freeze", "range.clear",
    "sheet.delete", "sheet.rename",
    "apply",
})


def _split_ref(ref: str) -> tuple[str, str]:
    """Split 'Sheet!CellOrRange' into (sheet_name, cell_ref)."""
    if "!" in ref:
        return ref.split("!", 1)
    return ("", ref)


def _resolve_ref(ctx: Any, ref: str, *, include_header: bool = True) -> tuple[str, str]:
    """Resolve a ref that may be 'Table[Column]' or 'Sheet!Range'.

    Tries ``resolve_table_column_ref`` first; falls back to ``_split_ref``.
    """
    from xl.adapters.openpyxl_engine import resolve_table_column_ref

    resolved = resolve_table_column_ref(ctx, ref, include_header=include_header)
    if resolved is not None:
        return resolved
    return _split_ref(ref)


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
        table_create,
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

        # Check step-level dry-run
        step_dry_run = workflow.defaults.dry_run or step.args.pop("dry_run", False) or step.args.pop("dry-run", False)
        if step.run in _MUTATING_STEPS and step_dry_run:
            step_result["ok"] = True
            step_result["result"] = {"status": "skipped", "reason": "dry-run"}
            results.append(step_result)
            continue

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
            elif step.run == "table.create":
                columns_arg = step.args.get("columns")
                change = table_create(
                    ctx,
                    step.args["sheet"],
                    step.args["table"],
                    step.args["ref"],
                    columns=columns_arg,
                    style=step.args.get("style", "TableStyleMedium2"),
                )
                mutated = True
                step_result["result"] = change.model_dump()
                step_result["ok"] = True

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
                cell_type = step.args.get("type")
                value = step.args["value"]
                if cell_type == "number" and isinstance(value, str):
                    try:
                        value = float(value)
                        if value == int(value):
                            value = int(value)
                    except ValueError:
                        pass
                elif cell_type == "bool" and isinstance(value, str):
                    value = value.lower() in ("true", "1", "yes")
                change = cell_set(
                    ctx, sheet_name, cell_ref, value,
                    cell_type=cell_type,
                    force_overwrite_formulas=step.args.get("force_overwrite_formulas", False),
                )
                mutated = True
                step_result["result"] = change.model_dump()
                step_result["ok"] = True

            elif step.run == "formula.set":
                ref = step.args["ref"]
                sheet_name, cell_ref = _resolve_ref(ctx, ref, include_header=False)
                change = formula_set(
                    ctx, sheet_name, cell_ref, step.args["formula"],
                    force_overwrite_values=step.args.get("force_overwrite_values", False),
                    force_overwrite_formulas=step.args.get("force_overwrite_formulas", False),
                    fill_mode=step.args.get("fill_mode", "relative"),
                )
                mutated = True
                step_result["result"] = change.model_dump()
                step_result["ok"] = True

            elif step.run == "format.number":
                ref = step.args.get("ref", "")
                sheet_name, range_ref = _resolve_ref(ctx, ref)
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
                if isinstance(columns, str):
                    columns = [c.strip().upper() for c in columns.split(",") if c.strip()]
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

            # -- Sheet / table delete --
            elif step.run == "sheet.delete":
                from xl.adapters.openpyxl_engine import sheet_delete
                change = sheet_delete(ctx, step.args["name"])
                mutated = True
                step_result["result"] = change.model_dump()
                step_result["ok"] = True

            elif step.run == "sheet.rename":
                from xl.adapters.openpyxl_engine import sheet_rename
                change = sheet_rename(ctx, step.args["name"], step.args["new_name"])
                mutated = True
                step_result["result"] = change.model_dump()
                step_result["ok"] = True

            elif step.run == "table.delete":
                from xl.adapters.openpyxl_engine import table_delete
                change = table_delete(ctx, step.args["table"])
                mutated = True
                step_result["result"] = change.model_dump()
                step_result["ok"] = True

            elif step.run == "table.delete_column":
                from xl.adapters.openpyxl_engine import table_delete_column
                change = table_delete_column(ctx, step.args["table"], step.args["name"])
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
                        elif op.type == "table.create":
                            change = table_create(ctx, op.sheet or "", op.table or "", op.ref or "",
                                                  columns=op.columns, style=op.style or "TableStyleMedium2")
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
        if not step_result.get("ok", False) and workflow.defaults.stop_on_error:
            break

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
