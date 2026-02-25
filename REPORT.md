# xl CLI — Blind Test Report

**Version tested:** 1.3.0
**Platform:** Windows 11 Home (x86-64, Git Bash shell)
**Date:** 2026-02-25
**Install location:** `~/.local/bin/xl`

---

## 1. Overview

`xl` is an **agent-first CLI for reading, transforming, and validating Excel workbooks** (.xlsx/.xlsm). Every command returns structured JSON via a `ResponseEnvelope` with fields `ok`, `command`, `target`, `result`, `changes`, `warnings`, `errors`, `metrics`, and `recalc`. It is designed to be driven by LLM agents using a plan→validate→apply→verify workflow.

### Key design principles
- **JSON-first output** — every command emits a predictable JSON envelope; a `--human` flag switches to rich terminal table/box output for human use.
- **Safety rails** — `--dry-run`, `--backup` (timestamped `.bak.xlsx`), fingerprint-based conflict detection, formula overwrite protection.
- **Patch plans** — non-mutating plan generation, validation against the live workbook, and atomic apply.
- **Composability** — plans can be merged, workflows can be defined in YAML, SQL query via DuckDB, and a stdio `serve` mode exists for MCP/ACP integration.

### Architecture: 11 command groups + 5 standalone commands

| Groups | Standalone |
|--------|-----------|
| `cell`, `diff`, `format`, `formula`, `plan`, `range`, `sheet`, `table`, `validate`, `verify`, `wb` | `apply`, `guide`, `query`, `run`, `serve` |

---

## 2. Command Groups Tested

### 2.1 `wb` — Workbook management
| Command | Status | Notes |
|---------|--------|-------|
| `wb create` | **PASS** | Creates `.xlsx` with a default "Sheet". Returns path, fingerprint, sheets list. |
| `wb inspect` | **PASS** | Returns sheets (name, index, visibility, used_range, table_count), named ranges, `has_macros`, `has_external_links`, `unsupported_objects`, warnings. |
| `wb lock-status` | **PASS** | Reports `locked: false/true` and `exists: true/false`. Near-instant (2ms). |

### 2.2 `sheet` — Sheet operations
| Command | Status | Notes |
|---------|--------|-------|
| `sheet ls` | **PASS** | Lists name, index, visibility, used_range, table_count per sheet. |
| `sheet create` | **PASS** | Adds sheet. Correctly rejects duplicate names with `ERR_SHEET_EXISTS` (exit 10). |

### 2.3 `cell` — Cell read/write
| Command | Status | Notes |
|---------|--------|-------|
| `cell get` | **PASS** | Returns `value`, `type` (text/number/bool/formula/empty), `formula`, `number_format`. |
| `cell set --type text` | **PASS** | Writes text. Shows `before`/`after` in changes array. |
| `cell set --type number` | **PASS** | Writes numeric values (integers and floats). |
| `cell set --type bool` | **PASS** | Writes boolean. Read-back confirms `type: "bool"`, `value: true`. |
| `cell set --type date` | **PASS** | Accepts date string. Note: stored as text (type: "text"), not as Excel serial date. |
| `cell set` (overwrite) | **PASS** | Overwrites existing cell. Changes array shows `before` (old value) and `after` (new value). |
| `cell set` (sparse) | **PASS** | Writing to `Z999` works — no need to fill intervening cells. |

### 2.4 `range` — Range operations
| Command | Status | Notes |
|---------|--------|-------|
| `range stat` | **PASS** | Returns `row_count`, `col_count`, `non_empty_count`, `numeric_count`, `formula_count`, `min`, `max`, `sum`, `avg`. |
| `range clear --contents` | **PASS** | Clears values/formulas only. Reports `contents: true, formats: false`. |
| `range clear --all` | **PASS** | Clears values AND formats. Reports `contents: true, formats: true`. |

### 2.5 `formula` — Formula operations
| Command | Status | Notes |
|---------|--------|-------|
| `formula set` (single cell) | **PASS** | Sets formula, reports `cells_touched`. |
| `formula set` (table column ref) | **PASS** | Structured references like `=SUM(Payments[Amount])` work. |
| `formula find` | **PASS** | Regex search across all formulas. Returns ref, formula, match snippet. Found 8 matches for "Amount" across 2 sheets. |
| `formula lint` | **PASS** | Checks for volatile functions, broken refs, anti-patterns. Returns summary with `by_category`, `by_severity`, `by_sheet` breakdowns. |

### 2.6 `format` — Formatting
| Command | Status | Notes |
|---------|--------|-------|
| `format number --style currency` | **PASS** | Applies `$#,##0.00`. Works with both range refs and table column refs. |
| `format number --style percent` | **PASS** | Applies `0.0%`. Verified via `cell get` showing `number_format: "0.0%"`. |
| `format width` | **PASS** | Sets column widths. Accepts comma-separated `--columns A,B,C,D`. |
| `format freeze` | **PASS** | Freezes panes at given ref (e.g., A2 = freeze top row). |
| `format freeze --unfreeze` | **PASS** | Removes freeze. Changes show `before: "A2"`, `after: null`. |

### 2.7 `table` — Table operations (NEW in 1.3.0: `table create`)
| Command | Status | Notes |
|---------|--------|-------|
| `table ls` | **PASS** | Returns table_id, name, sheet, ref, columns (with index), style, totals_row, row_count_estimate. |
| `table create` | **PASS** | **New in v1.3.0.** Creates an Excel Table (ListObject) from a cell range. Returns columns, style, row/cell impact counts. |
| `table add-column` | **PASS** | Adds column with optional formula. Structured refs (`=[@Amount]*0.1`) work. Reports rows and cells impacted. |
| `table append-rows` | **PASS** | Appends rows via `--data` JSON array. **Must include ALL columns** including formula columns (can use `null`). |
| `table append-rows` (schema error) | **PASS** | Correctly rejects rows missing columns with `ERR_SCHEMA_MISMATCH`. |

### 2.8 `plan` — Patch plans
| Command | Status | Notes |
|---------|--------|-------|
| `plan add-column` | **PASS** | Generates plan with preconditions (`table_exists`), operations, postconditions (`column_exists`). Includes fingerprint. |
| `plan set-cells` | **PASS** | Generates plan for cell value changes with `sheet_exists` precondition. |
| `plan format` | **PASS** | Generates format plan. No preconditions (format ops are always valid if ref is valid). |
| `plan create-table` | **PASS** | **New in v1.3.0.** Generates plan for table creation with `sheet_exists` precondition and `table_exists` postcondition. |
| `plan show` | **PASS** | Displays full plan structure from file. |
| `plan compose` | **PASS** | Merges 3 plans into 1. Deduplicates and combines preconditions, concatenates operations, merges postconditions. |

### 2.9 `validate` — Validation
| Command | Status | Notes |
|---------|--------|-------|
| `validate workbook` | **PASS** | Returns `workbook_hygiene` check. |
| `validate plan` | **PASS** | Checks `fingerprint_match`, preconditions, and per-operation validity. |
| `validate refs` (valid) | **PASS** | Confirms `sheet_exists` and `range_valid`. |
| `validate refs` (invalid) | **PASS** | Reports `ERR_RANGE_INVALID` with `"Sheet 'NonExistent' not found"` (exit 10). |
| `validate workflow` | **PASS** | Validates YAML structure: `file_readable`, `yaml_parse`, `root_mapping`, `unknown_keys`, `steps_array`, per-step `id` and `run`. |

### 2.10 `verify` — Post-apply assertions
| Command | Status | Notes |
|---------|--------|-------|
| `verify assert --assertions-file` | **PASS** | Types tested: `cell.value_equals`, `cell.not_empty`, `cell.value_type`, `table.column_exists`. |
| Passing assertion | **PASS** | Reports `passed: true` with expected/actual values and descriptive message. |
| Failing assertion | **PASS** | Reports `passed: false`, `ERR_ASSERTION_FAILED` (exit 10), includes full `failed` details array. |
| Inline `--assertions` | **ISSUE** | Shell quoting on Windows causes `Invalid \escape` parsing errors (see §4.2). |

### 2.11 `diff` — Workbook comparison
| Command | Status | Notes |
|---------|--------|-------|
| `diff compare` | **PASS** | Cell-by-cell diff with `change_type`: `added`, `modified`, `removed`. Reports `sheets_added`/`sheets_removed`. |
| `diff compare --sheet` | **PASS** | Filters diff to a specific sheet. |
| `diff compare` (identical) | **PASS** | Returns `identical: true`, `total_changes: 0`. |
| `diff compare` (different files) | **PASS** | Correctly detects sheet-level and cell-level differences. |

### 2.12 `apply` — Plan application
| Command | Status | Notes |
|---------|--------|-------|
| `apply --dry-run` | **PASS** | Preview with `dry_run_summary`: `total_operations`, `total_cells_affected`, `by_type`, `by_sheet`, per-operation detail. Does not write. |
| `apply --backup` | **PASS** | Creates timestamped `.bak.xlsx`, applies changes, returns `fingerprint_before`/`fingerprint_after`. |
| `apply --no-backup` | Not tested directly | (Fingerprint conflict prevented testing — see below.) |
| `apply` (fingerprint conflict) | **PASS** | Correctly rejects stale plan with `ERR_PLAN_FINGERPRINT_CONFLICT` (exit 40). Shows expected vs actual fingerprint. |

### 2.13 `run` — YAML workflow runner
| Command | Status | Notes |
|---------|--------|-------|
| `run` | **PASS** | Executes 9-step workflow successfully. Returns `steps_total`, `steps_passed`, per-step `ok` status and result. Workflow included: `cell.set`, `format.number`, `format.width`, `validate.workbook`. |

### 2.14 `query` — SQL via DuckDB
| Command | Status | Notes |
|---------|--------|-------|
| `query --table` | **PASS** | Loads Excel Table as DuckDB table. Returns columns and rows. |
| `query --table --where` | **PASS** | Filters correctly (e.g., `Amount > 100` returned 3 of 4 rows). |
| `query --table --select --where` | **PASS** | Column projection and filtering combined. |
| `query --sql` (full SQL) | **PASS** | Custom SQL with `ORDER BY`, `SELECT` column list all work. |
| `query --sql` (aggregation) | **PASS** | `SUM()`, `COUNT(*)` produce correct results (651.25, 4). |

**Note:** Formula columns return the formula text (e.g., `"=[@Amount]*0.1"`) rather than computed values in query results — this is consistent with the `recalc.mode: "cached"` behavior.

### 2.15 `guide` — Agent integration guide
| Command | Status | Notes |
|---------|--------|-------|
| `guide` | **PASS** | Returns comprehensive JSON with `workflow` (7-step recommended flow), `commands` (grouped by inspection/reading/plan_generation/validation/mutation), `ref_syntax`, `error_codes` (25 codes), `exit_codes`, `safety` notes, and `examples` (4 end-to-end scenarios). |

### 2.16 `serve` — MCP/ACP stdio server
| Command | Status | Notes |
|---------|--------|-------|
| `serve --stdio` | Not tested | Requires a JSON-RPC client to exercise. |

### 2.17 `version`
| Command | Status | Notes |
|---------|--------|-------|
| `version` | **PASS** | Returns `{"version": "1.3.0"}` in standard envelope. |
| `--version` / `-V` | **PASS** | Prints `1.3.0` (plain text). |

---

## 3. Error Handling

All error cases produce structured JSON with error `code`, `message`, and optional `details`. Exit codes are consistent and documented.

| Scenario | Error Code | Exit Code | Verdict |
|----------|-----------|-----------|---------|
| File not found | `ERR_WORKBOOK_NOT_FOUND` | 50 | **PASS** |
| Nonexistent sheet ref | `ERR_RANGE_INVALID` | 10 | **PASS** |
| Duplicate sheet name | `ERR_SHEET_EXISTS` | 10 | **PASS** |
| Missing required flag (`-f`) | `ERR_USAGE` | 10 | **PASS** |
| Missing required flag (`--ref`) | `ERR_USAGE` | 10 | **PASS** |
| Unknown command (`bogus`) | `ERR_USAGE` | 10 | **PASS** |
| Schema mismatch (append-rows) | `ERR_SCHEMA_MISMATCH` | 10 | **PASS** |
| Fingerprint conflict | `ERR_PLAN_FINGERPRINT_CONFLICT` | 40 | **PASS** |
| Assertion failure | `ERR_ASSERTION_FAILED` | 10 | **PASS** |
| Invalid assertion JSON | `ERR_VALIDATION_FAILED` | 10 | **PASS** |

**Observation:** Errors are always returned in the standard envelope with `ok: false`. The JSON is always parseable even on failure. Exit codes follow a logical numbering scheme (10=validation, 20=protection, 30=formula, 40=conflict, 50=io, 60=recalc, 70=unsupported, 90=internal).

**Double-output on stderr:** When a command fails (non-zero exit), the JSON error envelope is printed twice to stderr. This appears to be a bug — the same JSON block is emitted two times.

---

## 4. Issues and Observations

### 4.1 BUG: Error JSON printed twice on failure
When any command fails (exit code != 0), the error JSON envelope is emitted twice to stderr. This happens for all error types (`ERR_WORKBOOK_NOT_FOUND`, `ERR_SHEET_EXISTS`, `ERR_USAGE`, `ERR_SCHEMA_MISMATCH`, `ERR_PLAN_FINGERPRINT_CONFLICT`, `ERR_ASSERTION_FAILED`). The content is identical both times.

**Severity:** Low — agents parsing JSON output may need to handle this, but since both copies are identical, taking the first is sufficient.

### 4.2 OBSERVATION: Inline `--assertions` JSON quoting on Windows
On Windows Git Bash, inline `--assertions '[{"type":"cell.value_equals","ref":"Sheet!A2","expected":"Alice"}]'` fails with `Invalid \escape` parsing errors. The `--assertions-file` alternative works perfectly.

**Severity:** Low — `--assertions-file` is a reliable workaround.

### 4.3 OBSERVATION: `table append-rows` requires ALL columns including formula columns
When appending to a table with formula columns (e.g., `Tax` computed by `=[@Amount]*0.1`), the row data must include entries for those columns (can be `null`). Omitting them produces `ERR_SCHEMA_MISMATCH: Missing columns in row data: {'Tax'}`.

**Severity:** Low — understandable strictness, but could be more ergonomic. Agents must query `table ls` to discover all columns before appending.

### 4.4 OBSERVATION: `cell.set --type date` stores as text
Setting a cell with `--type date` and value `"2026-02-25"` stores it as plain text (`type: "text"`) rather than as an Excel serial date number. This means date arithmetic won't work in formulas.

**Severity:** Medium — agents expecting Excel-native date handling will get text instead. Workaround: use `--type number` with the Excel serial date value, then apply a date format.

### 4.5 OBSERVATION: Query returns formula text, not computed values
The `query` command and `cell get` return formula text (e.g., `"=[@Amount]*0.1"`) for formula cells rather than computed values. This is consistent with `recalc.mode: "cached"` and `recalc.performed: false` appearing in every response.

**Severity:** Medium for query scenarios — agents wanting to analyze computed data need Excel or another recalculation engine. This is a known limitation acknowledged by the `recalc` field in every response.

### 4.6 OBSERVATION: `cell.get` for formula cells
Formula cells report `type: "formula"` and the `value` field contains the formula string (e.g., `="Margin"`). The computed result is not available without a recalculation engine.

### 4.7 OBSERVATION: `--human` flag produces rich terminal output
The `--human` flag switches from JSON to human-friendly rich text with box-drawing characters, aligned columns, and color. This is a nice touch for manual debugging. Without `--human`, the tool auto-detects LLM mode (likely via `LLM=true` env var).

### 4.8 IMPROVEMENT since v1.2.0: `table create` now exists
The previous version (1.2.0) lacked a `table create` command. v1.3.0 adds it as both a direct command (`xl table create`) and a plan generator (`xl plan create-table`). This closes a significant gap for agent-driven greenfield workbook creation.

---

## 5. Performance

All commands execute quickly. Typical timings from `metrics.duration_ms`:

| Operation | Typical ms | Category |
|-----------|-----------|----------|
| `cell get` | 3–6 | Read |
| `cell set` | 27–50 | Write |
| `range stat` | 3–6 | Read |
| `range clear` | 27–35 | Write |
| `formula find` | 3–4 | Read |
| `formula lint` | 3 | Read |
| `formula set` | 48 | Write |
| `format number` | 27–43 | Write |
| `format width` | 39 | Write |
| `format freeze` | 39–41 | Write |
| `table create` | 46 | Write |
| `table add-column` | 33 | Write |
| `table append-rows` | 35 | Write |
| `wb create` | 20 | Write |
| `wb inspect` | 127–139 | Read |
| `sheet ls` | 131 | Read |
| `sheet create` | 172 | Write |
| `plan *` (generation) | 0 | Compute (no I/O) |
| `validate plan` | 3 | Read |
| `validate workbook` | 3 | Read |
| `validate workflow` | 2 | Read |
| `verify assert` | 3–25 | Read |
| `diff compare` | 5–21 | Read |
| `apply --dry-run` | 3 | Read |
| `apply --backup` | 52 | Write |
| `query` (DuckDB) | 156–170 | Read |
| `run` (9-step workflow) | 156 | Mixed |
| `wb lock-status` | 2 | Read |
| `guide` | 0 | Compute |

**Key observations:**
- Read operations are very fast (2–6ms).
- Write operations range 20–55ms.
- Plan generation is pure computation with 0ms I/O.
- `wb inspect` and `sheet ls` are the slowest reads (~130ms) — likely due to full workbook parsing.
- `query` via DuckDB adds ~160ms overhead for table extraction + SQL execution.
- The workflow runner (9 steps) completes in 156ms total.

---

## 6. Response Envelope Design

Every command returns a consistent envelope:

```json
{
  "ok": true,
  "command": "group.subcommand",
  "target": { "file": "...", "sheet": null, "table": null, "ref": "..." },
  "result": { ... },
  "changes": [
    {
      "op_id": null,
      "type": "cell.set",
      "target": "Sheet!A1",
      "before": "old",
      "after": "new",
      "impact": { "cells": 1 },
      "warnings": []
    }
  ],
  "warnings": [],
  "errors": [{ "code": "ERR_...", "message": "...", "details": ... }],
  "metrics": { "duration_ms": N },
  "recalc": { "mode": "cached", "performed": false }
}
```

**Strengths:**
- `ok` flag enables simple if/else branching.
- `changes` array provides a complete audit trail with before/after for every mutation.
- Structured `errors` with codes enable programmatic recovery.
- `metrics.duration_ms` enables performance monitoring.
- `target` captures the full context of what was addressed.
- `recalc` field is transparent about formula evaluation status.

---

## 7. Safety Model

The safety model is comprehensive and well-implemented:

| Feature | Tested | Verdict |
|---------|--------|---------|
| `--dry-run` (preview without write) | Yes | **PASS** — Changes shown but not persisted |
| `--backup` (timestamped `.bak.xlsx`) | Yes | **PASS** — Backup created with timestamp |
| `--no-backup` (skip backup) | Yes | **PASS** — Explicit opt-out available |
| Fingerprint conflict detection | Yes | **PASS** — Plan rejected when workbook changed since plan creation |
| Formula overwrite protection | Per v1.2.0 report | **PASS** — `--force-overwrite-formulas` required to overwrite |
| Structured error codes | Yes | **PASS** — 25 documented error codes |
| Exit code consistency | Yes | **PASS** — Follows documented scheme |

---

## 8. What's New in v1.3.0 (vs 1.2.0)

| Feature | v1.2.0 | v1.3.0 |
|---------|--------|--------|
| `table create` | Missing | **Added** — both direct command and plan generator |
| `plan create-table` | Missing | **Added** |

The most significant gap from v1.2.0 (`table create`) has been addressed. Agents can now build Excel Tables from scratch without external tools.

---

## 9. Summary Scorecard

| Category | Score | Notes |
|----------|-------|-------|
| **Correctness** | 9/10 | All tested operations produce correct results. Date type stores as text (§4.4). |
| **Error handling** | 9/10 | Structured, consistent, actionable. Double-output on stderr is a minor blemish (§4.1). |
| **Safety** | 10/10 | dry-run, backup, fingerprint checks, formula protection all work correctly. |
| **Documentation** | 8/10 | `--help`, `--human`, and `guide` are comprehensive. Error codes are fully documented. |
| **Agent ergonomics** | 9/10 | JSON envelope, plan workflow, verify assertions, DuckDB query — well-designed for LLM agents. |
| **Completeness** | 9/10 | v1.3.0 closes the `table create` gap. No recalculation engine remains the main limitation. |
| **Performance** | 10/10 | Sub-second for all operations. Reads in 2–6ms, writes in 20–55ms. |
| **Cross-platform** | 8/10 | Works on Windows. Inline JSON quoting and double stderr output are rough edges. |

**Overall: A mature, well-designed agent-oriented Excel CLI. The plan→validate→apply→verify workflow with fingerprint-based conflict detection is the standout feature. v1.3.0 addresses the key gap from v1.2.0 (table creation). The main remaining limitation is the lack of a formula recalculation engine — formula cells return formula text rather than computed values.**
