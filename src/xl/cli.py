"""Typer CLI application — top-level commands and subcommand groups."""

from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any, Optional

import typer

import xl
from xl.contracts.common import ChangeRecord, Target, WarningDetail
from xl.contracts.plans import (
    Operation,
    PatchPlan,
    PlanOptions,
    PlanTarget,
    Postcondition,
    Precondition,
)
from xl.contracts.responses import ApplyResult, ValidationResult
from xl.engine.dispatcher import (
    error_envelope,
    exit_code_for,
    print_response,
    success_envelope,
)
from xl.observe.events import Timer

# ---------------------------------------------------------------------------
# App & subcommand groups
# ---------------------------------------------------------------------------
app = typer.Typer(name="xl", help="Agent-first Excel CLI", no_args_is_help=True)

wb_app = typer.Typer(name="wb", help="Workbook operations", no_args_is_help=True)
sheet_app = typer.Typer(name="sheet", help="Sheet operations", no_args_is_help=True)
table_app = typer.Typer(name="table", help="Table operations", no_args_is_help=True)
cell_app = typer.Typer(name="cell", help="Cell operations", no_args_is_help=True)
range_app = typer.Typer(name="range", help="Range operations", no_args_is_help=True)
formula_app = typer.Typer(name="formula", help="Formula operations", no_args_is_help=True)
format_app = typer.Typer(name="format", help="Formatting operations", no_args_is_help=True)
query_app = typer.Typer(name="query", help="SQL-like table querying")
validate_app = typer.Typer(name="validate", help="Validation commands", no_args_is_help=True)
plan_app = typer.Typer(name="plan", help="Patch plan operations", no_args_is_help=True)
apply_app = typer.Typer(name="apply", help="Apply patch plans")
verify_app = typer.Typer(name="verify", help="Post-apply assertions")
diff_app = typer.Typer(name="diff", help="Compare workbook states")

app.add_typer(wb_app)
app.add_typer(sheet_app)
app.add_typer(table_app)
app.add_typer(cell_app)
app.add_typer(range_app)
app.add_typer(formula_app)
app.add_typer(format_app)
app.add_typer(validate_app)
app.add_typer(plan_app)

# Type aliases for common options
FilePath = Annotated[str, typer.Option("--file", "-f", help="Path to Excel workbook")]
JsonFlag = Annotated[bool, typer.Option("--json", help="JSON output")]
SheetOpt = Annotated[Optional[str], typer.Option("--sheet", "-s", help="Sheet name")]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _load_ctx(file: str, *, data_only: bool = False):
    from xl.engine.context import WorkbookContext
    return WorkbookContext(file, data_only=data_only)


def _emit(envelope, code=None):
    print_response(envelope)
    raise typer.Exit(code if code is not None else exit_code_for(envelope))


# ---------------------------------------------------------------------------
# xl version
# ---------------------------------------------------------------------------
@app.command()
def version():
    """Print version."""
    env = success_envelope("version", {"version": xl.__version__})
    _emit(env)


# ---------------------------------------------------------------------------
# xl wb inspect
# ---------------------------------------------------------------------------
@wb_app.command("inspect")
def wb_inspect(
    file: FilePath,
    json_out: JsonFlag = True,
):
    """Inspect workbook metadata."""
    with Timer() as t:
        try:
            ctx = _load_ctx(file)
            meta = ctx.get_workbook_meta()
            ctx.close()
        except FileNotFoundError:
            env = error_envelope("wb.inspect", "ERR_WORKBOOK_NOT_FOUND", f"File not found: {file}", target=Target(file=file))
            _emit(env)

    env = success_envelope(
        "wb.inspect",
        meta.model_dump(),
        target=Target(file=file),
        duration_ms=t.elapsed_ms,
    )
    if meta.warnings:
        env.warnings = [WarningDetail(code="WORKBOOK_WARNING", message=w) for w in meta.warnings]
    _emit(env)


# ---------------------------------------------------------------------------
# xl sheet ls
# ---------------------------------------------------------------------------
@sheet_app.command("ls")
def sheet_ls(
    file: FilePath,
    json_out: JsonFlag = True,
):
    """List sheets in a workbook."""
    with Timer() as t:
        try:
            ctx = _load_ctx(file)
            sheets = ctx.list_sheets()
            ctx.close()
        except FileNotFoundError:
            env = error_envelope("sheet.ls", "ERR_WORKBOOK_NOT_FOUND", f"File not found: {file}", target=Target(file=file))
            _emit(env)

    env = success_envelope(
        "sheet.ls",
        [s.model_dump() for s in sheets],
        target=Target(file=file),
        duration_ms=t.elapsed_ms,
    )
    _emit(env)


# ---------------------------------------------------------------------------
# xl table ls
# ---------------------------------------------------------------------------
@table_app.command("ls")
def table_ls(
    file: FilePath,
    sheet: SheetOpt = None,
    json_out: JsonFlag = True,
):
    """List tables in a workbook."""
    with Timer() as t:
        try:
            ctx = _load_ctx(file)
            tables = ctx.list_tables(sheet)
            ctx.close()
        except FileNotFoundError:
            env = error_envelope("table.ls", "ERR_WORKBOOK_NOT_FOUND", f"File not found: {file}", target=Target(file=file))
            _emit(env)

    env = success_envelope(
        "table.ls",
        [tb.model_dump() for tb in tables],
        target=Target(file=file, sheet=sheet),
        duration_ms=t.elapsed_ms,
    )
    _emit(env)


# ---------------------------------------------------------------------------
# xl table add-column
# ---------------------------------------------------------------------------
@table_app.command("add-column")
def table_add_column_cmd(
    file: FilePath,
    table: Annotated[str, typer.Option("--table", "-t", help="Table name")],
    name: Annotated[str, typer.Option("--name", "-n", help="New column name")],
    formula: Annotated[Optional[str], typer.Option("--formula", help="Column formula")] = None,
    default_value: Annotated[Optional[str], typer.Option("--default", help="Default value")] = None,
    backup: Annotated[bool, typer.Option("--backup", help="Create backup")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview only")] = False,
    json_out: JsonFlag = True,
):
    """Add a column to an Excel table."""
    from xl.adapters.openpyxl_engine import table_add_column
    from xl.io.fileops import backup as make_backup

    with Timer() as t:
        try:
            ctx = _load_ctx(file)
        except FileNotFoundError:
            env = error_envelope("table.add_column", "ERR_WORKBOOK_NOT_FOUND", f"File not found: {file}", target=Target(file=file))
            _emit(env)

        try:
            change = table_add_column(ctx, table, name, formula=formula, default_value=default_value)
        except ValueError as e:
            ctx.close()
            env = error_envelope("table.add_column", "ERR_TABLE_NOT_FOUND", str(e), target=Target(file=file, table=table))
            _emit(env)

        backup_path = None
        if not dry_run:
            if backup:
                backup_path = make_backup(file)
            ctx.save(file)
        ctx.close()

    result = {
        "dry_run": dry_run,
        "backup_path": backup_path,
    }
    env = success_envelope(
        "table.add_column",
        result,
        target=Target(file=file, table=table),
        changes=[change],
        duration_ms=t.elapsed_ms,
    )
    _emit(env)


# ---------------------------------------------------------------------------
# xl table append-rows
# ---------------------------------------------------------------------------
@table_app.command("append-rows")
def table_append_rows_cmd(
    file: FilePath,
    table: Annotated[str, typer.Option("--table", "-t", help="Table name")],
    data: Annotated[Optional[str], typer.Option("--data", help="Inline JSON array of row objects")] = None,
    data_file: Annotated[Optional[str], typer.Option("--data-file", help="Path to JSON file with rows")] = None,
    schema_mode: Annotated[str, typer.Option("--schema-mode", help="strict|allow-missing-null|map-by-header")] = "strict",
    backup: Annotated[bool, typer.Option("--backup", help="Create backup")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview only")] = False,
    json_out: JsonFlag = True,
):
    """Append rows to an Excel table."""
    from xl.adapters.openpyxl_engine import table_append_rows

    # Parse row data
    if data:
        rows = json.loads(data)
    elif data_file:
        rows = json.loads(Path(data_file).read_text())
    else:
        env = error_envelope("table.append_rows", "ERR_MISSING_DATA", "Provide --data or --data-file", target=Target(file=file, table=table))
        _emit(env)
        return  # unreachable due to _emit raising

    with Timer() as t:
        try:
            ctx = _load_ctx(file)
        except FileNotFoundError:
            env = error_envelope("table.append_rows", "ERR_WORKBOOK_NOT_FOUND", f"File not found: {file}", target=Target(file=file))
            _emit(env)

        try:
            change = table_append_rows(ctx, table, rows, schema_mode=schema_mode)
        except ValueError as e:
            ctx.close()
            code = "ERR_SCHEMA_MISMATCH" if "columns" in str(e).lower() else "ERR_TABLE_NOT_FOUND"
            env = error_envelope("table.append_rows", code, str(e), target=Target(file=file, table=table))
            _emit(env)

        backup_path = None
        if not dry_run:
            if backup:
                from xl.io.fileops import backup as make_backup
                backup_path = make_backup(file)
            ctx.save(file)
        ctx.close()

    result = {"dry_run": dry_run, "backup_path": backup_path}
    env = success_envelope(
        "table.append_rows",
        result,
        target=Target(file=file, table=table),
        changes=[change],
        duration_ms=t.elapsed_ms,
    )
    _emit(env)


# ---------------------------------------------------------------------------
# xl cell set
# ---------------------------------------------------------------------------
@cell_app.command("set")
def cell_set_cmd(
    file: FilePath,
    ref: Annotated[str, typer.Option("--ref", help="Cell reference (e.g. Sheet1!B2)")],
    value: Annotated[str, typer.Option("--value", help="Value to set")],
    cell_type: Annotated[Optional[str], typer.Option("--type", help="number|text|bool")] = None,
    force_overwrite_formulas: Annotated[bool, typer.Option("--force-overwrite-formulas")] = False,
    backup: Annotated[bool, typer.Option("--backup")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    json_out: JsonFlag = True,
):
    """Set a cell value."""
    from xl.adapters.openpyxl_engine import cell_set

    # Parse sheet!ref
    if "!" in ref:
        sheet_name, cell_ref = ref.split("!", 1)
    else:
        env = error_envelope("cell.set", "ERR_RANGE_INVALID", "Ref must include sheet name (e.g. Sheet1!B2)", target=Target(file=file))
        _emit(env)
        return

    # Coerce value
    parsed_value: Any = value
    if cell_type == "number":
        try:
            parsed_value = float(value)
            if parsed_value == int(parsed_value):
                parsed_value = int(parsed_value)
        except ValueError:
            pass
    elif cell_type == "bool":
        parsed_value = value.lower() in ("true", "1", "yes")

    with Timer() as t:
        try:
            ctx = _load_ctx(file)
        except FileNotFoundError:
            env = error_envelope("cell.set", "ERR_WORKBOOK_NOT_FOUND", f"File not found: {file}", target=Target(file=file))
            _emit(env)

        try:
            change = cell_set(ctx, sheet_name, cell_ref, parsed_value, cell_type=cell_type, force_overwrite_formulas=force_overwrite_formulas)
        except (ValueError, KeyError) as e:
            ctx.close()
            code = "ERR_FORMULA_OVERWRITE_BLOCKED" if "formula" in str(e).lower() else "ERR_RANGE_INVALID"
            env = error_envelope("cell.set", code, str(e), target=Target(file=file, ref=ref))
            _emit(env)

        backup_path = None
        if not dry_run:
            if backup:
                from xl.io.fileops import backup as make_backup
                backup_path = make_backup(file)
            ctx.save(file)
        ctx.close()

    result = {"dry_run": dry_run, "backup_path": backup_path}
    env = success_envelope(
        "cell.set",
        result,
        target=Target(file=file, ref=ref),
        changes=[change],
        duration_ms=t.elapsed_ms,
    )
    _emit(env)


# ---------------------------------------------------------------------------
# xl validate workbook
# ---------------------------------------------------------------------------
@validate_app.command("workbook")
def validate_workbook_cmd(
    file: FilePath,
    json_out: JsonFlag = True,
):
    """Validate workbook health."""
    from xl.validation.validators import validate_workbook

    with Timer() as t:
        try:
            ctx = _load_ctx(file)
            result = validate_workbook(ctx)
            ctx.close()
        except FileNotFoundError:
            env = error_envelope("validate.workbook", "ERR_WORKBOOK_NOT_FOUND", f"File not found: {file}", target=Target(file=file))
            _emit(env)

    env = success_envelope(
        "validate.workbook",
        result.model_dump(),
        target=Target(file=file),
        duration_ms=t.elapsed_ms,
    )
    _emit(env)


# ---------------------------------------------------------------------------
# xl validate plan
# ---------------------------------------------------------------------------
@validate_app.command("plan")
def validate_plan_cmd(
    file: FilePath,
    plan_path: Annotated[str, typer.Option("--plan", help="Path to plan JSON file")],
    json_out: JsonFlag = True,
):
    """Validate a patch plan against a workbook."""
    from xl.validation.validators import validate_plan

    try:
        plan_data = json.loads(Path(plan_path).read_text())
        plan = PatchPlan(**plan_data)
    except Exception as e:
        env = error_envelope("validate.plan", "ERR_PLAN_INVALID", f"Cannot parse plan: {e}", target=Target(file=file))
        _emit(env)
        return

    with Timer() as t:
        try:
            ctx = _load_ctx(file)
            result = validate_plan(ctx, plan)
            ctx.close()
        except FileNotFoundError:
            env = error_envelope("validate.plan", "ERR_WORKBOOK_NOT_FOUND", f"File not found: {file}", target=Target(file=file))
            _emit(env)

    env = success_envelope(
        "validate.plan",
        result.model_dump(),
        target=Target(file=file),
        duration_ms=t.elapsed_ms,
    )
    if not result.valid:
        env.ok = False
        env.errors = [
            _err_from_check(c) for c in result.checks if not c.get("passed", True)
        ]
    _emit(env)


def _err_from_check(check: dict) -> Any:
    from xl.contracts.common import ErrorDetail
    return ErrorDetail(
        code=f"ERR_{check.get('type', 'UNKNOWN').upper()}",
        message=check.get("message", "Check failed"),
    )


# ---------------------------------------------------------------------------
# xl plan show
# ---------------------------------------------------------------------------
@plan_app.command("show")
def plan_show(
    plan_path: Annotated[str, typer.Option("--plan", help="Path to plan JSON file")],
    json_out: JsonFlag = True,
):
    """Display a patch plan."""
    try:
        plan_data = json.loads(Path(plan_path).read_text())
        plan = PatchPlan(**plan_data)
    except Exception as e:
        env = error_envelope("plan.show", "ERR_PLAN_INVALID", f"Cannot parse plan: {e}")
        _emit(env)
        return

    env = success_envelope("plan.show", plan.model_dump())
    _emit(env)


# ---------------------------------------------------------------------------
# xl plan add-column
# ---------------------------------------------------------------------------
@plan_app.command("add-column")
def plan_add_column(
    file: FilePath,
    table: Annotated[str, typer.Option("--table", "-t", help="Table name")],
    name: Annotated[str, typer.Option("--name", "-n", help="Column name")],
    formula: Annotated[Optional[str], typer.Option("--formula")] = None,
    default_value: Annotated[Optional[str], typer.Option("--default")] = None,
    append: Annotated[Optional[str], typer.Option("--append", help="Append to existing plan file")] = None,
    json_out: JsonFlag = True,
):
    """Generate a plan to add a column to a table."""
    from xl.io.fileops import fingerprint

    fp = fingerprint(file) if Path(file).exists() else None
    plan_id = f"pln_{datetime.now(timezone.utc).strftime('%Y%m%d')}_{uuid.uuid4().hex[:8]}"

    op = Operation(
        op_id=f"op_{uuid.uuid4().hex[:6]}",
        type="table.add_column",
        table=table,
        name=name,
        formula=formula,
        value=default_value,
    )
    pre = Precondition(type="table_exists", table=table)
    post = Postcondition(type="column_exists", table=table, column=name)

    if append and Path(append).exists():
        existing = PatchPlan(**json.loads(Path(append).read_text()))
        existing.operations.append(op)
        existing.preconditions.append(pre)
        existing.postconditions.append(post)
        plan = existing
    else:
        plan = PatchPlan(
            plan_id=plan_id,
            target=PlanTarget(file=file, fingerprint=fp),
            preconditions=[pre],
            operations=[op],
            postconditions=[post],
        )

    env = success_envelope("plan.add_column", plan.model_dump(), target=Target(file=file, table=table))
    _emit(env)


# ---------------------------------------------------------------------------
# xl plan set-cells
# ---------------------------------------------------------------------------
@plan_app.command("set-cells")
def plan_set_cells(
    file: FilePath,
    ref: Annotated[str, typer.Option("--ref", help="Cell ref (Sheet!A1)")],
    value: Annotated[str, typer.Option("--value", help="Value")],
    cell_type: Annotated[Optional[str], typer.Option("--type")] = None,
    json_out: JsonFlag = True,
):
    """Generate a plan to set cell values."""
    from xl.io.fileops import fingerprint

    fp = fingerprint(file) if Path(file).exists() else None
    plan_id = f"pln_{datetime.now(timezone.utc).strftime('%Y%m%d')}_{uuid.uuid4().hex[:8]}"

    sheet_name = ""
    cell_ref = ref
    if "!" in ref:
        sheet_name, cell_ref = ref.split("!", 1)

    parsed_value: Any = value
    if cell_type == "number":
        try:
            parsed_value = float(value)
        except ValueError:
            pass

    op = Operation(
        op_id=f"op_{uuid.uuid4().hex[:6]}",
        type="cell.set",
        sheet=sheet_name,
        ref=cell_ref,
        value=parsed_value,
        cell_type=cell_type,
    )

    plan = PatchPlan(
        plan_id=plan_id,
        target=PlanTarget(file=file, fingerprint=fp),
        preconditions=[Precondition(type="sheet_exists", sheet=sheet_name)] if sheet_name else [],
        operations=[op],
    )

    env = success_envelope("plan.set_cells", plan.model_dump(), target=Target(file=file, ref=ref))
    _emit(env)


# ---------------------------------------------------------------------------
# xl plan format
# ---------------------------------------------------------------------------
@plan_app.command("format")
def plan_format(
    file: FilePath,
    ref: Annotated[str, typer.Option("--ref", help="Range ref or TableName[Column]")],
    style: Annotated[str, typer.Option("--style", help="number|percent|currency|date")] = "number",
    decimals: Annotated[int, typer.Option("--decimals")] = 2,
    append: Annotated[Optional[str], typer.Option("--append", help="Append to existing plan file")] = None,
    json_out: JsonFlag = True,
):
    """Generate a plan for number formatting."""
    from xl.io.fileops import fingerprint

    fp = fingerprint(file) if Path(file).exists() else None

    op = Operation(
        op_id=f"op_{uuid.uuid4().hex[:6]}",
        type="format.number",
        ref=ref,
        style=style,
        decimals=decimals,
    )

    if append and Path(append).exists():
        existing = PatchPlan(**json.loads(Path(append).read_text()))
        existing.operations.append(op)
        plan = existing
    else:
        plan_id = f"pln_{datetime.now(timezone.utc).strftime('%Y%m%d')}_{uuid.uuid4().hex[:8]}"
        plan = PatchPlan(
            plan_id=plan_id,
            target=PlanTarget(file=file, fingerprint=fp),
            operations=[op],
        )

    env = success_envelope("plan.format", plan.model_dump(), target=Target(file=file, ref=ref))
    _emit(env)


# ---------------------------------------------------------------------------
# xl plan compose
# ---------------------------------------------------------------------------
@plan_app.command("compose")
def plan_compose(
    plans: Annotated[list[str], typer.Option("--plan", help="Plan files to merge")],
    json_out: JsonFlag = True,
):
    """Merge multiple plan files into one."""
    merged_ops: list[Operation] = []
    merged_pre: list[Precondition] = []
    merged_post: list[Postcondition] = []
    target_file = ""
    fp = None

    for p in plans:
        data = json.loads(Path(p).read_text())
        plan = PatchPlan(**data)
        if not target_file:
            target_file = plan.target.file
            fp = plan.target.fingerprint
        merged_ops.extend(plan.operations)
        merged_pre.extend(plan.preconditions)
        merged_post.extend(plan.postconditions)

    plan_id = f"pln_{datetime.now(timezone.utc).strftime('%Y%m%d')}_{uuid.uuid4().hex[:8]}"
    composed = PatchPlan(
        plan_id=plan_id,
        target=PlanTarget(file=target_file, fingerprint=fp),
        preconditions=merged_pre,
        operations=merged_ops,
        postconditions=merged_post,
    )

    env = success_envelope("plan.compose", composed.model_dump(), target=Target(file=target_file))
    _emit(env)


# ---------------------------------------------------------------------------
# xl apply
# ---------------------------------------------------------------------------
@app.command("apply")
def apply_cmd(
    file: FilePath,
    plan_path: Annotated[str, typer.Option("--plan", help="Path to plan JSON file")],
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview without applying")] = False,
    do_backup: Annotated[bool, typer.Option("--backup/--no-backup", help="Create backup before applying")] = True,
    json_out: JsonFlag = True,
):
    """Apply a patch plan to a workbook."""
    from xl.adapters.openpyxl_engine import (
        cell_set,
        format_number,
        resolve_table_column_ref,
        table_add_column,
        table_append_rows,
    )
    from xl.io.fileops import backup as make_backup
    from xl.io.fileops import fingerprint
    from xl.validation.validators import validate_plan

    # Load plan
    try:
        plan_data = json.loads(Path(plan_path).read_text())
        plan = PatchPlan(**plan_data)
    except Exception as e:
        env = error_envelope("apply", "ERR_PLAN_INVALID", f"Cannot parse plan: {e}", target=Target(file=file))
        _emit(env)
        return

    with Timer() as t:
        # Load workbook
        try:
            ctx = _load_ctx(file)
        except FileNotFoundError:
            env = error_envelope("apply", "ERR_WORKBOOK_NOT_FOUND", f"File not found: {file}", target=Target(file=file))
            _emit(env)
            return

        fp_before = ctx.fp

        # Fingerprint conflict check
        if plan.target.fingerprint and plan.options.fail_on_external_change:
            if plan.target.fingerprint != fp_before:
                ctx.close()
                env = error_envelope(
                    "apply", "ERR_PLAN_FINGERPRINT_CONFLICT",
                    "Workbook fingerprint changed since plan was created",
                    target=Target(file=file),
                    details={"expected": plan.target.fingerprint, "actual": fp_before},
                )
                _emit(env)
                return

        # Validate plan
        val_result = validate_plan(ctx, plan)
        if not val_result.valid:
            ctx.close()
            env = error_envelope(
                "apply", "ERR_VALIDATION_FAILED",
                "Plan validation failed",
                target=Target(file=file),
                details={"checks": val_result.checks},
            )
            _emit(env)
            return

        # Execute operations
        changes: list[ChangeRecord] = []
        for op in plan.operations:
            try:
                if op.type == "table.add_column":
                    change = table_add_column(ctx, op.table, op.name, formula=op.formula, default_value=op.value)
                    changes.append(change)
                elif op.type == "table.append_rows":
                    change = table_append_rows(ctx, op.table, op.rows or [], schema_mode=op.schema_mode or "strict")
                    changes.append(change)
                elif op.type == "cell.set":
                    sheet_name = op.sheet or ""
                    change = cell_set(ctx, sheet_name, op.ref or "", op.value, force_overwrite_formulas=op.force_overwrite_formulas)
                    changes.append(change)
                elif op.type == "format.number":
                    ref_str = op.ref or ""
                    sheet_name = ""
                    actual_ref = ref_str
                    # Resolve table column refs
                    resolved = resolve_table_column_ref(ctx, ref_str)
                    if resolved:
                        sheet_name, actual_ref = resolved
                    elif "!" in ref_str:
                        sheet_name, actual_ref = ref_str.split("!", 1)

                    if sheet_name:
                        change = format_number(ctx, sheet_name, actual_ref, style=op.style or "number", decimals=op.decimals or 2)
                        changes.append(change)
                else:
                    changes.append(ChangeRecord(
                        op_id=op.op_id,
                        type=op.type,
                        target=str(op.ref or op.table or ""),
                        after={"status": "skipped", "reason": f"Unsupported operation type: {op.type}"},
                    ))
            except Exception as e:
                ctx.close()
                env = error_envelope(
                    "apply", "ERR_OPERATION_FAILED",
                    f"Operation {op.op_id} failed: {e}",
                    target=Target(file=file),
                )
                _emit(env)
                return

        # Save
        backup_path = None
        fp_after = None
        if not dry_run:
            if do_backup:
                backup_path = make_backup(file)
            ctx.save(file)
            fp_after = fingerprint(file)
        ctx.close()

    result = ApplyResult(
        applied=not dry_run,
        dry_run=dry_run,
        backup_path=backup_path,
        operations_applied=len(changes),
        fingerprint_before=fp_before,
        fingerprint_after=fp_after,
    )

    env = success_envelope(
        "apply",
        result.model_dump(),
        target=Target(file=file),
        changes=changes,
        duration_ms=t.elapsed_ms,
    )
    _emit(env)


# ---------------------------------------------------------------------------
# xl query
# ---------------------------------------------------------------------------
@app.command("query")
def query_cmd(
    file: FilePath,
    sql: Annotated[Optional[str], typer.Option("--sql", help="SQL query")] = None,
    table: Annotated[Optional[str], typer.Option("--table", "-t", help="Table name")] = None,
    where: Annotated[Optional[str], typer.Option("--where", help="WHERE clause")] = None,
    select: Annotated[Optional[str], typer.Option("--select", help="Comma-separated columns")] = None,
    json_out: JsonFlag = True,
):
    """Query table data using SQL (via DuckDB)."""
    import duckdb

    with Timer() as t:
        try:
            ctx = _load_ctx(file, data_only=True)
        except FileNotFoundError:
            env = error_envelope("query", "ERR_WORKBOOK_NOT_FOUND", f"File not found: {file}", target=Target(file=file))
            _emit(env)
            return

        # Build SQL if not provided directly
        if sql is None:
            if table is None:
                ctx.close()
                env = error_envelope("query", "ERR_MISSING_PARAM", "Provide --sql or --table", target=Target(file=file))
                _emit(env)
                return
            cols = select if select else "*"
            sql = f"SELECT {cols} FROM {table}"
            if where:
                sql += f" WHERE {where}"

        # Extract all tables to DuckDB
        conn = duckdb.connect()
        tables_found = ctx.list_tables()
        for tbl in tables_found:
            ws = ctx.wb[tbl.sheet]
            from xl.adapters.openpyxl_engine import _parse_ref
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
                conn.execute(f"CREATE TABLE \"{tbl.name}\" AS SELECT * FROM data_rows")

        try:
            result = conn.execute(sql).fetchdf()
            columns = list(result.columns)
            rows = result.to_dict(orient="records")
            row_count = len(rows)
        except Exception as e:
            ctx.close()
            conn.close()
            env = error_envelope("query", "ERR_QUERY_FAILED", str(e), target=Target(file=file))
            _emit(env)
            return

        conn.close()
        ctx.close()

    from xl.contracts.responses import QueryResult
    qr = QueryResult(columns=columns, rows=rows, row_count=row_count)
    env = success_envelope(
        "query",
        qr.model_dump(),
        target=Target(file=file),
        duration_ms=t.elapsed_ms,
    )
    _emit(env)


# ---------------------------------------------------------------------------
# Entrypoint (for `python -m xl`)
# ---------------------------------------------------------------------------
def main() -> None:
    app()


if __name__ == "__main__":
    main()
