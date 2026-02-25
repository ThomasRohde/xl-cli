"""Workflow engine for ``xl run`` — executes YAML workflow specs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from xl.contracts.workflow import WorkflowSpec


def load_workflow(path: str | Path) -> WorkflowSpec:
    """Load a workflow spec from a YAML file."""
    text = Path(path).read_text()
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


def execute_workflow(
    workflow: WorkflowSpec,
    workbook_path: str | Path,
) -> dict[str, Any]:
    """Execute a workflow against a workbook. Returns combined results."""
    from xl.adapters.openpyxl_engine import (
        cell_set,
        formula_set,
        table_add_column,
        table_append_rows,
    )
    from xl.engine.context import WorkbookContext
    from xl.validation.validators import validate_plan

    results: list[dict[str, Any]] = []
    ctx = WorkbookContext(workbook_path)
    mutated = False

    for step in workflow.steps:
        step_result: dict[str, Any] = {"step_id": step.id, "run": step.run}
        try:
            if step.run == "table.ls":
                tables = ctx.list_tables(step.args.get("sheet"))
                step_result["result"] = [t.model_dump() for t in tables]
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
                sheet_name, cell_ref = ref.split("!", 1) if "!" in ref else ("", ref)
                change = cell_set(ctx, sheet_name, cell_ref, step.args["value"])
                mutated = True
                step_result["result"] = change.model_dump()
                step_result["ok"] = True

            elif step.run == "formula.set":
                ref = step.args["ref"]
                sheet_name, cell_ref = ref.split("!", 1) if "!" in ref else ("", ref)
                change = formula_set(
                    ctx, sheet_name, cell_ref, step.args["formula"],
                    force_overwrite_values=step.args.get("force_overwrite_values", False),
                    force_overwrite_formulas=step.args.get("force_overwrite_formulas", False),
                )
                mutated = True
                step_result["result"] = change.model_dump()
                step_result["ok"] = True

            elif step.run == "validate.plan":
                from xl.contracts.plans import PatchPlan
                plan_data = step.args.get("plan")
                if isinstance(plan_data, str):
                    plan_data = json.loads(Path(plan_data).read_text())
                plan = PatchPlan(**plan_data)
                vr = validate_plan(ctx, plan)
                step_result["result"] = vr.model_dump()
                step_result["ok"] = vr.valid

            elif step.run == "verify.assert":
                from xl.engine.verify import run_assertions
                assertions = step.args.get("assertions", [])
                assertion_results = run_assertions(ctx, assertions)
                step_result["result"] = assertion_results
                step_result["ok"] = all(r.get("passed", False) for r in assertion_results)

            elif step.run == "wb.inspect":
                meta = ctx.get_workbook_meta()
                step_result["result"] = meta.model_dump()
                step_result["ok"] = True

            elif step.run == "sheet.ls":
                sheets = ctx.list_sheets()
                step_result["result"] = [s.model_dump() for s in sheets]
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
