# Implementation Plan: `xl` Agent-First Excel CLI

## Overview

Implement the `xl` CLI as described in `xl-agent-cli-prd.md`. This is a Python-based, agent-first CLI for Excel workbooks using `openpyxl`, `Typer`, `Pydantic v2`, and supporting libraries. The plan follows the PRD's milestone structure, targeting the v1 slice outlined in Section 30.

---

## Phase 1: Foundation (Milestone 0) — COMPLETE

### Step 1.1 — Project scaffolding ✅
### Step 1.2 — Source package structure ✅
### Step 1.3 — Response envelope and error taxonomy ✅
### Step 1.4 — CLI framework + global flags ✅
### Step 1.5 — Workbook context and fingerprinting ✅
### Step 1.6 — `xl wb inspect` ✅
### Step 1.7 — `xl sheet ls` ✅
### Step 1.8 — `xl version` ✅
### Step 1.9 — Test infrastructure ✅

---

## Phase 2: Table Operations + Patch Plans (Milestone 1) — COMPLETE

### Step 2.1 — `xl table ls` ✅
### Step 2.2 — `xl table add-column` ✅
### Step 2.3 — `xl table append-rows` ✅
### Step 2.4 — Patch plan schema + `xl plan show` ✅
### Step 2.5 — Plan generators ✅
### Step 2.6 — `xl apply --dry-run` and `xl apply` ✅
### Step 2.7 — Tests for table operations and patch lifecycle ✅

---

## Phase 3: Formula + Cell/Range + Formatting (Milestone 3) — THIS SESSION

This phase fills out the remaining cell/range escape hatches, formula operations, and formatting commands from the PRD.

### Step 3.1 — `xl formula set`

**File changes**: `src/xl/adapters/openpyxl_engine.py`, `src/xl/cli.py`

Add a `formula_set` function in the adapter:
- Set formulas for a cell, range, or table column
- Parameters: `--file`, `--ref` (Sheet!A1, Sheet!A1:A10, or TableName[Column]), `--formula`, `--force-overwrite-values`, `--force-overwrite-formulas`
- If ref targets a range, fill the formula into all cells in that range
- If ref targets a table column (TableName[Column]), fill formula into all data rows
- Resolve table column refs using existing `resolve_table_column_ref()`
- Overwrite safeguards: block if existing cell has a value (unless `--force-overwrite-values`) or formula (unless `--force-overwrite-formulas`)
- Return `ChangeRecord` with cells_touched count

Wire `xl formula set` command in `cli.py`:
- Uses `formula_app` subcommand group (already registered)
- Options: `--file`, `--ref`, `--formula`, `--force-overwrite-values`, `--force-overwrite-formulas`, `--backup`, `--dry-run`, `--json`

### Step 3.2 — `xl formula lint`

**File changes**: `src/xl/adapters/openpyxl_engine.py`, `src/xl/cli.py`

Add a `formula_lint` function in the adapter:
- Scan all cells in a sheet (or workbook) for formula issues
- Heuristic checks (no evaluation):
  1. **Volatile functions**: detect `OFFSET`, `INDIRECT`, `NOW`, `TODAY`, `RAND`, `RANDBETWEEN` usage
  2. **Broken refs**: detect `#REF!` in formula text
  3. **Mixed patterns**: detect adjacent cells with inconsistent formula structures (e.g. A1 has `=B1+C1` but A2 has `=B2*C2`)
  4. **Suspicious literals**: detect hardcoded numbers in formula regions where formulas are expected
- Return a list of lint findings, each with: cell ref, category, severity (warning/info), message
- Support `--sheet` filter to limit scope

Wire `xl formula lint` in `cli.py`:
- Options: `--file`, `--sheet` (optional), `--json`
- Returns envelope with result containing list of lint findings

### Step 3.3 — `xl formula find`

**File changes**: `src/xl/adapters/openpyxl_engine.py`, `src/xl/cli.py`

Add a `formula_find` function in the adapter:
- Search workbook for formulas matching a regex pattern
- Parameters: sheet (optional filter), pattern (regex string)
- Return list of matches: cell ref (Sheet!A1), formula text, match snippet
- Support `--pattern` flag for regex search (e.g. `--pattern "VLOOKUP"`)

Wire `xl formula find` in `cli.py`:
- Options: `--file`, `--pattern`, `--sheet` (optional), `--json`

### Step 3.4 — `xl cell get`

**File changes**: `src/xl/adapters/openpyxl_engine.py`, `src/xl/cli.py`

Add a `cell_get` function in the adapter:
- Read cell value by ref (Sheet!A1)
- Return: value, type (str/int/float/bool/datetime/formula), formula text if formula, number_format
- Support `--data-only` flag to read cached formula values instead of formula text

Wire `xl cell get` in `cli.py`:
- Options: `--file`, `--ref`, `--data-only`, `--json`

### Step 3.5 — `xl range stat`

**File changes**: `src/xl/adapters/openpyxl_engine.py`, `src/xl/cli.py`

Add a `range_stat` function in the adapter:
- Compute statistics for a range (Sheet!A1:F500)
- Stats: row_count, col_count, non_empty_count, numeric_count, formula_count, min, max, sum, avg (for numeric cells)
- Support `--data-only` for cached values

Wire `xl range stat` in `cli.py`:
- Options: `--file`, `--ref`, `--data-only`, `--json`

### Step 3.6 — `xl range clear`

**File changes**: `src/xl/adapters/openpyxl_engine.py`, `src/xl/cli.py`

Add a `range_clear` function in the adapter:
- Clear a range of cells
- Modes: `--contents` (values + formulas), `--formats` (number formats, styles), `--all` (both)
- Return `ChangeRecord` with cells_cleared count

Wire `xl range clear` in `cli.py`:
- Options: `--file`, `--ref`, `--contents`, `--formats`, `--all`, `--backup`, `--dry-run`, `--json`

### Step 3.7 — `xl format` commands

**File changes**: `src/xl/adapters/openpyxl_engine.py`, `src/xl/cli.py`

Existing: `format_number()` already handles number/percent/currency/date formatting.

Add new formatting operations:

**`xl format width`** — Set column widths:
- Function `format_width(ctx, sheet, columns, width)` in adapter
- Options: `--file`, `--sheet`, `--columns` (e.g. "A,B,C" or "A:F"), `--width` (float), `--auto` (auto-fit based on content length)

**`xl format freeze`** — Freeze panes:
- Function `format_freeze(ctx, sheet, ref)` in adapter
- Options: `--file`, `--sheet`, `--ref` (cell below and right of frozen area, e.g. "B2" freezes row 1 and column A)
- Also support `--unfreeze` to remove freeze

Wire these as subcommands of `format_app`:
- `xl format number` (already exists via `format_number` in adapter — needs CLI wiring)
- `xl format width`
- `xl format freeze`

### Step 3.8 — `xl validate refs`

**File changes**: `src/xl/validation/validators.py`, `src/xl/cli.py`

Add a `validate_refs` function:
- Validate that a reference (Sheet!A1:D10) points to valid cells
- Check: sheet exists, range within used area, cells not empty (optional)

Wire `xl validate refs` in `cli.py`:
- Options: `--file`, `--ref`, `--json`

### Step 3.9 — Tests for Phase 3

**File changes**: `tests/test_adapter.py`, `tests/test_cli.py` (extend existing)

Add tests for:
- `formula set` — set formula on cell, range, table column; test overwrite guards
- `formula lint` — detect volatile functions, broken refs
- `formula find` — search formulas by pattern
- `cell get` — read cell values and types
- `range stat` — compute range statistics
- `range clear` — clear contents/formats
- `format width` — set column widths
- `format freeze` — freeze/unfreeze panes
- `validate refs` — reference validation

---

## Phase 4: Verify, Diff, and Policy (Milestone 2 completion)

### Step 4.1 — `xl verify` post-apply assertions

**File changes**: `src/xl/engine/verify.py` (new), `src/xl/cli.py`

Create verification engine:
- Assertion types:
  - `table.column_exists` — column exists in table
  - `table.row_count` — table has expected row count (exact, min, max)
  - `cell.value_equals` — cell value matches expected
  - `cell.value_type` — cell value type matches expected
  - `cell.not_empty` — cell is not empty
  - `range.non_empty_count` — non-empty cell count in range
- Input: `--file`, `--assertions` (inline JSON), or `--assertions-file` (JSON file)
- Return: list of assertion results (passed/failed, expected, actual, message)

### Step 4.2 — `xl diff` workbook comparison

**File changes**: `src/xl/diff/differ.py`, `src/xl/cli.py`

Implement workbook diff:
- Compare two workbook files (or a workbook before/after apply)
- Diff output: list of cell-level changes (ref, before_value, after_value, change_type: added/removed/modified)
- Options: `--file-a`, `--file-b`, `--sheet` (optional filter), `--json`
- Group changes by sheet, then by type
- Include metadata diff (sheets added/removed, tables added/removed)

### Step 4.3 — Policy engine

**File changes**: `src/xl/validation/policy.py` (new), `src/xl/validation/validators.py`

Implement policy loading and enforcement:
- Load `xl-policy.yaml` from `--config` path or current directory
- Policy schema:
  ```yaml
  protected_sheets: [Sheet1]
  protected_ranges: ["Sheet1!A1:A10"]
  mutation_thresholds:
    max_cells: 10000
    max_rows: 5000
  allowed_commands: [wb.inspect, sheet.ls, table.ls, validate.*]
  redaction:
    mask_columns: [SSN, Password]
  ```
- Integrate policy checks into `validate_plan()` and `apply_cmd()`
- Return warnings/errors for policy violations

### Step 4.4 — `xl wb lock-status`

**File changes**: `src/xl/cli.py`

Wire the existing `check_lock()` from `io/fileops.py`:
- `xl wb lock-status --file budget.xlsx --json`
- Return lock status in standard envelope

### Step 4.5 — Tests for Phase 4

Add tests for verify assertions, diff comparison, policy enforcement, lock status.

---

## Phase 5: Workflows + Observability (Milestone 4)

### Step 5.1 — `xl run` workflow execution

**File changes**: `src/xl/engine/workflow.py` (new), `src/xl/cli.py`

Implement workflow engine:
- Parse YAML workflow spec (WorkflowSpec model already defined)
- Execute steps sequentially
- Support step references (`from_step`) to pass outputs between steps
- Map step `run` values to internal command functions:
  - `table.ls` → `ctx.list_tables()`
  - `plan.compose` → create PatchPlan from operations list
  - `validate.plan` → `validate_plan(ctx, plan)`
  - `apply.plan` → apply plan operations
  - `verify.assert` → run assertions
- Collect results per step and return combined workflow result
- Respect `defaults` (output format, recalc mode, dry_run)

Wire `xl run` in `cli.py`:
- Options: `--file` (YAML workflow path), `--json`
- Alias: `app.command("run")`

### Step 5.2 — Event stream (`--emit-events`)

**File changes**: `src/xl/observe/events.py`, `src/xl/cli.py`

Extend the observe module:
- `EventEmitter` class that writes NDJSON events to stderr (to keep stdout for JSON responses)
- Lifecycle events per PRD Section 20:
  - `workbook_opened`, `workbook_scanned`, `tables_detected`
  - `plan_validated`, `dry_run_completed`, `patch_applied`
  - `recalc_started`, `recalc_finished`, `workbook_saved`
- Each event: `{"event": "...", "timestamp": "...", "data": {...}}`
- Wire global `--emit-events` flag to enable event emission
- Thread the emitter through commands via a context variable or callback

### Step 5.3 — Trace mode (`--trace`)

**File changes**: `src/xl/observe/events.py`, `src/xl/cli.py`

Implement trace file generation:
- `TraceRecorder` class that collects trace data during execution
- Trace file contents per PRD Section 20:
  - Command args (sanitized: file path only, no content)
  - Normalized target references
  - Pre/post fingerprints
  - Validation report summary
  - Applied operations summary
  - Timing breakdown (total, per-operation)
- Wire global `--trace` flag: when set, writes `{workbook}.trace.json` alongside the workbook

### Step 5.4 — `xl serve --stdio` (optional)

**File changes**: `src/xl/server/stdio.py`, `src/xl/cli.py`

Implement basic stdio server:
- Read line-delimited JSON requests from stdin
- Each request: `{"id": "...", "command": "table.ls", "args": {"file": "...", "sheet": "..."}}`
- Dispatch to same engine functions as CLI commands
- Write JSON response per line to stdout
- Session management: keep WorkbookContext open across requests for same file
- `xl serve --stdio` starts the server loop

### Step 5.5 — Tests for Phase 5

Add tests for:
- Workflow execution (end-to-end YAML workflow)
- Event stream output format
- Trace file generation and content
- stdio server request/response cycle

---

## Phase 6: Hardening (Milestone 5)

### Step 6.1 — Golden workbook fixtures
- Create `tests/fixtures/workbooks/` with pre-built .xlsx files covering edge cases:
  - Workbook with hidden sheets
  - Workbook with named ranges
  - Workbook with multiple tables across sheets
  - Workbook with formulas (volatile, broken refs, mixed patterns)
  - Workbook with various number formats
  - Large workbook (1000+ rows)

### Step 6.2 — Property-based tests
- Use `hypothesis` for:
  - Plan generation → apply → verify round-trip
  - Random cell values → set → get consistency
  - Table append → row count correctness

### Step 6.3 — Performance testing
- Test with large workbooks (10K+ rows)
- Ensure read-only mode is used for inspection commands
- Profile and optimize hot paths

### Step 6.4 — Cross-platform verification
- Verify file locking on Linux
- Document platform-specific behavior

---

## Implementation Notes

- **Develop on branch**: `claude/continue-prd-4NQv5`
- **Python version**: 3.12+
- **Package manager**: `uv`
- **Build system**: `hatchling`
- **All commands** return the standard `ResponseEnvelope` JSON
- **Exit codes** follow the taxonomy in PRD Section 19
- **Testing**: pytest with fixtures, golden outputs, and property-based tests

## Scope for This Session

This session implements **Phase 3** (Formula, Cell/Range, Formatting) and **Phase 4** (Verify, Diff, Policy) and **Phase 5** (Workflows, Observability), bringing the CLI to feature-complete v1 status. Phase 6 (Hardening) will be addressed as part of the implementation through incremental tests alongside each feature.
